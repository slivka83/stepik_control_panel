"""Shared helpers for the raw-sync package.

The package keeps a single public facade: ``app.services.raw_sync``.  Every
helper that other modules (or tests) may want to replace is re-exported there.
Cross-module calls go through :func:`_hub` so patching the facade — e.g.
``patch("app.services.raw_sync._request")`` — keeps working exactly as it did
when this was one module.
"""

import json
import logging
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

API_PAGE_SIZE = 20

# Preferred natural-key column for upsert conflict resolution per raw table.
# The serial `id` column is intentionally excluded; objects are identified by
# their business key (submission_id, attempt_id, comment_id, etc.).
_NATURAL_KEYS = {
    "raw_submission": "submission_id",
    "raw_attempt": "attempt_id",
    "raw_comment": "comment_id",
    "raw_certificate": "certificate_id",
    "raw_course_review": "review_id",
    "raw_course_review_summary": "review_summary_id",
}


def _hub():
    """Return the package module (the stable public facade)."""
    return sys.modules[__package__]


def _query_params(extra: dict | None = None, page: int = 1) -> dict:
    p = {"page": page, "page_size": API_PAGE_SIZE}
    if extra:
        p.update(extra)
    return p


def _is_text_step(raw_json) -> bool:
    """Является ли шаг теоретическим (text-блок, на нём нет решений).

    `_raw_json` — dict (PG jsonb) или JSON-строка (SQLite TEXT), обрабатываем оба.
    """
    if isinstance(raw_json, (str, bytes, bytearray)):
        try:
            raw = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return False
    else:
        raw = raw_json
    if not isinstance(raw, dict):
        return False
    block = raw.get("block")
    return isinstance(block, dict) and block.get("name") == "text"


async def _paginated_fetch(
    path: str,
    token: str,
    key: str,
    extra: dict | None = None,
    max_pages: int = 500,
) -> list[dict]:
    all_items = []
    page = 1
    while page <= max_pages:
        data = await _hub()._request("GET", path, token, _query_params(extra, page))
        items = data.get(key, [])
        if not items:
            break
        all_items.extend(items)
        if not data.get("meta", {}).get("has_next"):
            break
        page += 1
    return all_items


async def _get_fields_mapping(session: AsyncSession, endpoint_name: str) -> dict[str, str]:
    r = await session.execute(
        text("""
            SELECT api_field, db_column FROM meta_field_mapping
            WHERE endpoint_name = :ep AND is_loaded = True
        """),
        {"ep": endpoint_name},
    )
    return {row[0]: row[1] for row in r}


async def _sync_id_sequence(session: AsyncSession, raw_table: str) -> None:
    """PG: после INSERT с явными id подтянуть serial-последовательность.

    Иначе следующий INSERT без id (upsert-путь) получит nextval из прошлой
    жизни и упадёт на pkey. SQLite это не трогает (нет sequences).
    """
    try:
        r = await session.execute(text(f'SELECT max(id) FROM "{raw_table}"'))
        max_id = r.scalar()
        if max_id:
            await session.execute(
                text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :m, true)"),
                {"t": raw_table, "m": int(max_id)},
            )
    except Exception:
        pass


async def _replace_raw_table(session: AsyncSession, raw_table: str, objects: list[dict], mapping: dict[str, str]):
    if not objects:
        return

    try:
        col_r = await session.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t
        """),
            {"t": raw_table},
        )
        table_cols = {row[0] for row in col_r}
    except Exception:
        table_cols = set()

    all_db_cols = [c for c in mapping.values() if not table_cols or c in table_cols]

    try:
        pk_r = await session.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND column_default LIKE 'nextval(%'
        """),
            {"t": raw_table},
        )
        serial_pks = {row[0] for row in pk_r}
    except Exception:
        serial_pks = set()

    col_names = [c for c in all_db_cols if c not in serial_pks] + ["_raw_json"]
    if not col_names:
        return

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    try:
        await session.execute(text(f'TRUNCATE TABLE "{raw_table}" RESTART IDENTITY CASCADE'))
    except Exception:
        await session.execute(text(f'DELETE FROM "{raw_table}"'))

    for obj in objects:
        raw_json = json.dumps(obj, ensure_ascii=False)
        values = {"_raw_json": raw_json}
        for c in col_names:
            if c == "_raw_json":
                continue
            api_field = next((k for k, v in mapping.items() if v == c), c)
            val = obj.get(api_field)
            if val is not None and isinstance(val, (dict, list)):
                values[c] = json.dumps(val, ensure_ascii=False)
            elif val is not None:
                values[c] = str(val)
            else:
                values[c] = None
        await session.execute(
            text(f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders})'),
            values,
        )

    await _sync_id_sequence(session, raw_table)


async def _upsert_raw_table(
    session: AsyncSession,
    raw_table: str,
    objects: list[dict],
    mapping: dict[str, str],
    extra_columns: dict[str, object] | None = None,
):
    """INSERT ... ON CONFLICT для incremental-синков.

    extra_columns — контекстные значения, которых нет в ответе API
    (например, step для submissions: известен только из ?step=).
    """
    if not objects:
        return

    try:
        col_r = await session.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t
        """),
            {"t": raw_table},
        )
        table_cols = {row[0] for row in col_r}
    except Exception:
        table_cols = set()

    all_db_cols = [c for c in mapping.values() if not table_cols or c in table_cols]
    if extra_columns:
        all_db_cols += [c for c in extra_columns if c not in all_db_cols]

    try:
        pk_r = await session.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND column_default LIKE 'nextval(%'
        """),
            {"t": raw_table},
        )
        serial_pks = {row[0] for row in pk_r}
    except Exception:
        serial_pks = set()

    col_names = [c for c in all_db_cols if c not in serial_pks] + ["_raw_json"]
    if not col_names:
        return

    # Если id исключён (serial PK), новые строки получат nextval — он обязан
    # быть за пределами занятого диапазона (см. регрессию raw_comment_pkey)
    if serial_pks:
        await _sync_id_sequence(session, raw_table)

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    # Determine the conflict target: the table's business/natural key if known,
    # otherwise the first *_id column present in the insert.
    id_field = _NATURAL_KEYS.get(raw_table)
    if id_field not in col_names:
        id_field = next((c for c in col_names if c.endswith("_id")), None)

    conflict_clause = f' ON CONFLICT ("{id_field}") DO NOTHING' if id_field else ""

    for obj in objects:
        raw_json = json.dumps(obj, ensure_ascii=False)
        values = {"_raw_json": raw_json}
        for c in col_names:
            if c == "_raw_json":
                continue
            if extra_columns and c in extra_columns:
                values[c] = extra_columns[c]
                continue
            api_field = next((k for k, v in mapping.items() if v == c), c)
            val = obj.get(api_field)
            if val is not None and isinstance(val, (dict, list)):
                values[c] = json.dumps(val, ensure_ascii=False)
            elif val is not None:
                values[c] = str(val)
            else:
                values[c] = None
        await session.execute(
            text(f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders}){conflict_clause}'),
            values,
        )

    await _sync_id_sequence(session, raw_table)


async def _save_sync_state(session: AsyncSession, endpoint: str, key: str, value: str) -> None:
    """Upsert one incremental-sync cursor (raw_sync_state)."""
    await session.execute(
        text(
            "INSERT INTO raw_sync_state (endpoint_name, key, value) "
            "VALUES (:ep, :k, :v) "
            "ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"
        ),
        {"ep": endpoint, "k": key, "v": value, "v2": value},
    )


async def _raw_course_ids(session: AsyncSession) -> list[int]:
    r = await session.execute(text("SELECT course_id FROM raw_course"))
    return [int(row[0]) for row in r if row[0] is not None]
