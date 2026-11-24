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
    "raw_promo_code": "promo_code_id",
}

# Контекстные колонки, которых нет в ответе API: их нельзя затирать NULL
# upsert'ом из другого прохода (author pass не знает step).
_CONTEXT_COLUMNS = {"step"}


def _hub():
    """Return the package module (the stable public facade)."""
    return sys.modules[__package__]


def _as_int(value) -> int | None:
    """int() без исключения: мусор в raw-строке не должен ронять синк."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_by(objects: list[dict], *fields: str) -> list[dict]:
    """Убрать повторы API-объектов по бизнес-ключу (страницы могли пересечься).

    Объекты без полного ключа не склеиваем: иначе несколько записей с
    отсутствующим id превратились бы в одну.
    """
    seen: set[tuple[str, ...]] = set()
    result: list[dict] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        values = tuple(obj.get(field) for field in fields)
        if not values or any(value is None for value in values):
            result.append(obj)
            continue
        key = tuple(str(value) for value in values)
        if key in seen:
            continue
        seen.add(key)
        result.append(obj)
    return result


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


class RawSyncTruncatedError(RuntimeError):
    """API kept saying has_next after the page cap — data would be incomplete."""


async def _paginated_fetch(
    path: str,
    token: str,
    key: str,
    extra: dict | None = None,
    max_pages: int = 500,
) -> list[dict]:
    all_items: list[dict] = []
    page = 1
    while page <= max_pages:
        data = await _hub()._request("GET", path, token, _query_params(extra, page))
        if not isinstance(data, dict):
            logger.error("  %s: unexpected response %r", path, type(data).__name__)
            raise RawSyncTruncatedError(f"{path}: unexpected response {type(data).__name__}")
        items = data.get(key, [])
        if not isinstance(items, list):
            logger.error("  %s: unexpected %r payload (not a list)", path, type(items).__name__)
            raise RawSyncTruncatedError(f"{path}: unexpected payload {type(items).__name__}")
        if not items:
            return all_items
        all_items.extend(item for item in items if isinstance(item, dict))
        meta = data.get("meta") if isinstance(data, dict) else None
        if not (isinstance(meta, dict) and meta.get("has_next")):
            return all_items
        page += 1
    else:
        # Ответ оборвался на предохранителе. Не отдаём неполный список
        # вызывающему full-reload: иначе он заменит таблицу частичными данными.
        logger.error("  %s: page limit %d reached — refusing to replace with partial data", path, max_pages)
        raise RawSyncTruncatedError(f"{path}: page limit {max_pages} reached")
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


async def _table_columns(session: AsyncSession, raw_table: str) -> set[str]:
    """Columns of the real table (empty on SQLite/unknown — use all mapped)."""
    try:
        rows = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = current_schema()"
            ),
            {"t": raw_table},
        )
        return {row[0] for row in rows}
    except Exception:
        return set()


async def _serial_columns(session: AsyncSession, raw_table: str) -> set[str]:
    """Serial/identity primary keys must not be inserted explicitly."""
    try:
        rows = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = current_schema() "
                "AND column_default LIKE 'nextval(%'"
            ),
            {"t": raw_table},
        )
        return {row[0] for row in rows}
    except Exception:
        return set()


def _build_columns(
    mapping: dict[str, str],
    table_cols: set[str],
    serial_cols: set[str],
    extra_columns: dict[str, object] | None = None,
) -> list[str]:
    cols = [c for c in mapping.values() if not table_cols or c in table_cols]
    if extra_columns:
        cols += [c for c in extra_columns if c not in cols]
    cols = [c for c in dict.fromkeys(cols) if c not in serial_cols]
    if "_raw_json" not in cols:
        cols.append("_raw_json")
    return cols


def _build_row_values(
    obj: dict,
    col_names: list[str],
    mapping: dict[str, str],
    extra_columns: dict[str, object] | None = None,
) -> dict:
    """One INSERT row: mapped API fields (strings) + the full `_raw_json`."""
    values: dict[str, object] = {"_raw_json": json.dumps(obj, ensure_ascii=False)}
    reverse: dict[str, str] = {}
    for api_field, db_col in mapping.items():
        # First mapped API field wins (same rule as the old next(...) lookup).
        reverse.setdefault(db_col, api_field)
    for col in col_names:
        if col == "_raw_json":
            continue
        if extra_columns and col in extra_columns:
            values[col] = extra_columns[col]
            continue
        val = obj.get(reverse.get(col, col))
        if val is None:
            values[col] = None
        elif isinstance(val, (dict, list)):
            values[col] = json.dumps(val, ensure_ascii=False)
        else:
            values[col] = str(val)
    return values


async def _replace_raw_table(session: AsyncSession, raw_table: str, objects: list[dict], mapping: dict[str, str]):
    """Full reload: the API answer is the whole truth for the table.

    An empty `objects` clears the table instead of silently keeping stale rows:
    otherwise an entity removed on Stepik (or an empty endpoint) would survive
    in the raw layer and in every mart built from it, forever.
    """
    objects = objects or []

    table_cols = await _table_columns(session, raw_table)
    serial_cols = await _serial_columns(session, raw_table)
    col_names = _build_columns(mapping, table_cols, serial_cols)

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    # DELETE, а не TRUNCATE: на PostgreSQL неудачный TRUNCATE переводит
    # транзакцию в aborted, и fallback-DELETE уже не выполнится. Таблицы raw-
    # слоя небольшие (крупные — incremental и не заменяются целиком).
    await session.execute(text(f'DELETE FROM "{raw_table}"'))

    if objects:
        # executemany: одна сетевая операция на всю таблицу вместо INSERT на
        # каждую строку (raw_user — тысячи профилей, это были тысячи round-trip).
        values = [_build_row_values(obj, col_names, mapping) for obj in objects]
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

    table_cols = await _table_columns(session, raw_table)
    serial_cols = await _serial_columns(session, raw_table)
    col_names = _build_columns(mapping, table_cols, serial_cols, extra_columns)

    # Если id исключён (serial PK), новые строки получат nextval — он обязан
    # быть за пределами занятого диапазона (см. регрессию raw_comment_pkey)
    if serial_cols:
        await _sync_id_sequence(session, raw_table)

    placeholders = ", ".join(f":{c}" for c in col_names)
    cols_str = ", ".join(f'"{c}"' for c in col_names)

    # Determine the conflict target: the table's business/natural key if known,
    # otherwise the first *_id column present in the insert.
    id_field = _NATURAL_KEYS.get(raw_table)
    if id_field not in col_names:
        id_field = next((c for c in col_names if c.endswith("_id")), None)
    # Do UPDATE, not DO NOTHING: comments and reviews are editable on Stepik
    # (text, likes/vote_delta, replies, is_staff_replied). DO NOTHING kept the
    # first copy forever, so the "Не отвеченные"/"Дизлайки" tabs drifted from
    # the platform. Context columns absent from the API payload (e.g. `step`
    # for author-pass submissions) keep their stored value via COALESCE.
    conflict_clause = ""
    if id_field:
        assignments = []
        for col in col_names:
            if col == id_field:
                continue
            if (extra_columns and col in extra_columns) or col in _CONTEXT_COLUMNS:
                assignments.append(f'"{col}" = COALESCE(EXCLUDED."{col}", "{raw_table}"."{col}")')
            else:
                assignments.append(f'"{col}" = EXCLUDED."{col}"')
        if assignments:
            conflict_clause = f' ON CONFLICT ("{id_field}") DO UPDATE SET {", ".join(assignments)}'

    values = [_build_row_values(obj, col_names, mapping, extra_columns) for obj in objects]
    await session.execute(
        text(f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders}){conflict_clause}'),
        values,
    )


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
    return sorted({int(row[0]) for row in r if row[0] is not None})


async def _previous_raw_objects(
    session: AsyncSession, raw_table: str, key_column: str, keys
) -> list[dict]:
    """Сохранить строки, которые не удалось перезагрузить.

    `_replace_raw_table` работает по принципу «ответ API — вся правда», но при
    частично упавшем запросе (один курс/батч вернул ошибку) это удаляло бы уже
    загруженные данные этого курса. Возвращаем их из `_raw_json`, чтобы
    вставить обратно вместе со свежими строками успешных запросов.
    """
    values = sorted({str(k) for k in keys if k is not None})
    if not values:
        return []
    placeholders = ", ".join(f":k{i}" for i in range(len(values)))
    r = await session.execute(
        text(f'SELECT _raw_json FROM "{raw_table}" WHERE "{key_column}" IN ({placeholders})'),
        {f"k{i}": value for i, value in enumerate(values)},
    )
    objects = []
    for (raw,) in r:
        try:
            obj = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(obj, dict):
            objects.append(obj)
    return objects
