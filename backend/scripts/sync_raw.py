"""
Sync raw tables from Stepik API according to meta_endpoint strategy.

Usage:
    python scripts/sync_raw.py                    # sync all active endpoints
    python scripts/sync_raw.py submissions        # sync specific endpoint
    python scripts/sync_raw.py courses sections   # sync multiple
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.crypto import decrypt_token
from app.services.raw_sync.common import _NATURAL_KEYS
from app.services.stepik_api import StepikAPIError, _request, get_finance_token, get_user_profile

settings = get_settings()


def _parse_time(value) -> datetime | None:
    """ISO-время Stepik → aware datetime (сравнение строк даёт ложный порядок)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


IDS_SOURCE_MAP = {
    "sections": ("raw_course", "section_ids"),
    "units": ("raw_section", "units"),
    "lessons": ("raw_unit", "lesson_id"),
    "steps": ("raw_lesson", "steps"),
    "course_review_summaries": ("raw_course", "review_summary_json"),
    "progresses": ("raw_step", "progress"),
    "users": ("__multi__", "user"),
    "profiles": ("raw_user", "profile"),
}
STEP_COURSE_ENDPOINTS = {"submissions"}  # per-course author submission pass


async def get_user_token() -> str | None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT access_token FROM users ORDER BY created_at ASC, id ASC LIMIT 1")
        )
        row = r.fetchone()
    await engine.dispose()
    if row:
        return decrypt_token(row[0])
    return None


async def get_client_token() -> str | None:
    if not settings.stepik_finance_client_id:
        return None
    return await get_finance_token(settings.stepik_finance_client_id, settings.stepik_finance_client_secret)


def clean_path(api_path: str) -> str:
    m = re.search(r"/api/([a-z][a-z0-9-]*)", api_path)
    if m:
        return "/" + m.group(1)
    return api_path


async def fetch_page(path: str, token: str, params: dict | None = None) -> dict:
    """Shared Stepik GET: retries/429/rate limit and the GET-only guard."""
    return await _request("GET", path, token, params)


async def resolve_ids(engine, endpoint_name: str) -> list[str]:
    src = IDS_SOURCE_MAP.get(endpoint_name)
    if not src:
        return []
    raw_table, field = src
    if raw_table == "__multi__":
        queries = {
            "user": [
                "SELECT DISTINCT student_id FROM student_enrollments WHERE student_id IS NOT NULL",
                "SELECT DISTINCT user_id FROM submissions WHERE user_id IS NOT NULL",
                "SELECT DISTINCT user_id FROM raw_course_grade WHERE user_id IS NOT NULL",
                "SELECT DISTINCT user_id FROM raw_certificate WHERE user_id IS NOT NULL",
                'SELECT DISTINCT "user" FROM raw_course_review WHERE "user" IS NOT NULL',
                'SELECT DISTINCT "user" FROM raw_comment WHERE "user" IS NOT NULL',
            ],
        }
        seen = set()
        ids = []
        async with engine.begin() as conn:
            for q in queries.get(field, []):
                try:
                    r = await conn.execute(text(q))
                    for row in r:
                        sid = str(row[0])
                        if sid.lstrip("-").isdigit() and sid not in seen:
                            seen.add(sid)
                            ids.append(sid)
                except Exception:
                    continue
        return ids
    seen = set()
    ids = []
    async with engine.begin() as conn:
        r = await conn.execute(text(f'SELECT "{field}" FROM "{raw_table}"'))
        for row in r:
            val = row[0]
            if val is None:
                continue
            try:
                items = json.loads(val) if isinstance(val, str) else val
            except (json.JSONDecodeError, TypeError):
                items = [str(val)] if val else []
            if not isinstance(items, (list, tuple)):
                items = [items]
            for item in items:
                sid = str(item)
                # Extract numeric ID from URL patterns like /api/progresses/123456
                url_match = re.search(r"/api/\w+/(\d+)", sid)
                if url_match:
                    sid = url_match.group(1)
                if sid not in seen:
                    seen.add(sid)
                    ids.append(sid)
    return ids


async def get_course_ids(engine) -> list[str]:
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT course_id FROM raw_course ORDER BY course_id"))
        return [str(row[0]) for row in r if row[0] is not None]


async def get_step_ids(engine) -> list[str]:
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT step_id FROM raw_step ORDER BY step_id"))
        return [str(row[0]) for row in r if row[0] is not None]


def extract_objects(data: dict, api_path: str) -> list[dict]:
    for key in data:
        if key != "meta":
            return data[key]
    return []


async def sync_full_reload(
    engine,
    token,
    endpoint: dict,
    raw_table: str,
    api_path: str,
):
    """Full paginated reload (DELETE + INSERT). Determines query mode from api_path."""
    clean = clean_path(api_path)
    ep_name = endpoint["endpoint_name"]

    # Determine query mode from api_path in meta_endpoint. `/courses` seeded
    # without `?teacher=` would otherwise take the bare branch and replace the
    # table with the global Stepik catalogue (first ~400 courses), wiping the
    # author's raw data.
    mode = None  # "ids", "course", "step", "teacher", None (bare)
    if ep_name == "courses" or "?teacher=" in api_path:
        mode = "teacher"
    elif "?ids[]=" in api_path:
        mode = "ids"
    elif "?course=" in api_path:
        mode = "course"
    elif "?step=" in api_path:
        mode = "step"

    if mode == "ids":
        ids = await resolve_ids(engine, ep_name)
        if not ids:
            # Bare endpoint для ids[]-эндпоинта вернул бы глобальные объекты
            # (sections/lessons без фильтра) и затёр бы таблицу ими.
            print(f"  {raw_table}: no ID source — skip")
            return
        batch_size = 100
        all_objects = []
        capped = False
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            page = 1
            max_pages = 500
            while page <= max_pages:
                data = await fetch_page(clean, token, {"ids[]": batch, "page": page})
                objects = extract_objects(data, api_path)
                if not objects:
                    break
                all_objects.extend(objects)
                if not data.get("meta", {}).get("has_next"):
                    break
                page += 1
                await asyncio.sleep(0.3)
            else:
                capped = True
            print(f"    ... {len(all_objects)} records")
        if capped:
            print(f"  {raw_table}: остановлено на лимите страниц — таблица НЕ перезаписана")
            return
        # Empty answer clears the table: full reload means the API is the
        # whole truth, stale rows must not survive.
        await _replace_table(engine, raw_table, all_objects)
        print(f"  {raw_table}: {len(all_objects)} rows (full_reload, ids[])")
        return

    if mode == "course":
        course_ids = await get_course_ids(engine)
        if not course_ids:
            print(f"  {raw_table}: no courses")
            return
        all_objects = []
        capped = False
        max_pages = 500
        for cid in course_ids:
            page = 1
            while page <= max_pages:
                try:
                    data = await fetch_page(clean, token, {"course": cid, "page": page})
                except StepikAPIError as e:
                    if e.status_code == 404:
                        print(f"    course {cid}: 404 — skip")
                        break
                    raise
                objects = extract_objects(data, api_path)
                if not objects:
                    break
                all_objects.extend(objects)
                meta = data.get("meta", {})
                if not meta.get("has_next"):
                    break
                page += 1
                await asyncio.sleep(0.3)
            else:
                capped = True
            print(f"    course {cid}: {len(all_objects)} total")
        if capped:
            print(f"  {raw_table}: остановлено на лимите страниц — таблица НЕ перезаписана")
            return
        await _replace_table(engine, raw_table, all_objects)
        print(f"  {raw_table}: {len(all_objects)} rows (full_reload, course)")
        return

    if mode == "step":
        step_ids = await get_step_ids(engine)
        if not step_ids:
            print(f"  {raw_table}: no steps")
            return
        all_objects = []
        capped = False
        for sid in step_ids:
            page = 1
            max_pages = 500
            while page <= max_pages:
                data = await fetch_page(clean, token, {"step": sid, "page": page})
                objects = extract_objects(data, api_path)
                if not objects:
                    break
                all_objects.extend(objects)
                meta = data.get("meta", {})
                if not meta.get("has_next"):
                    break
                page += 1
                await asyncio.sleep(0.3)
            else:
                capped = True
        if capped:
            print(f"  {raw_table}: остановлено на лимите страниц — таблица НЕ перезаписана")
            return
        print(f"    {len(all_objects)} total")
        await _replace_table(engine, raw_table, all_objects)
        print(f"  {raw_table}: {len(all_objects)} rows (full_reload, step)")
        return

    if mode == "teacher":
        teacher_id = get_settings().stepik_user_id
        if not teacher_id:
            # Fresh install / STEPIK_USER_ID=0: владельца даёт токен
            # (/stepics/1). ?teacher=0 вернул бы пустой список и затёр курсы.
            profile = await get_user_profile(token)
            try:
                teacher_id = int(profile.get("user")) if isinstance(profile, dict) else 0
            except (TypeError, ValueError):
                teacher_id = 0
        if not teacher_id:
            print("  SKIP: cannot resolve course author (STEPIK_USER_ID/token)")
            return
        all_objects = []
        page = 1
        max_pages = 200
        capped = False
        while page <= max_pages:
            data = await fetch_page(clean, token, {"teacher": teacher_id, "page": page})
            objects = extract_objects(data, api_path)
            if not objects:
                break
            all_objects.extend(objects)
            meta = data.get("meta", {})
            if not meta.get("has_next"):
                break
            page += 1
            await asyncio.sleep(0.3)
        else:
            capped = True
        if capped:
            print(f"  {raw_table}: остановлено на лимите страниц — таблица НЕ перезаписана")
            return
        await _replace_table(engine, raw_table, all_objects)
        print(f"  {raw_table}: {len(all_objects)} rows (full_reload, teacher={teacher_id})")
        return

    # Bare endpoint — paginate (max 20 pages = ~400 records at 20/page)
    all_objects = []
    page = 1
    max_pages = 20
    capped = False
    while page <= max_pages:
        data = await fetch_page(clean, token, {"page": page})
        objects = extract_objects(data, api_path)
        if not objects:
            break
        all_objects.extend(objects)
        meta = data.get("meta", {})
        if not meta.get("has_next"):
            break
        page += 1
        await asyncio.sleep(0.3)
    else:
        capped = True
    if capped:
        print(f"  {raw_table}: остановлено на лимите страниц — таблица НЕ перезаписана")
        return
    await _replace_table(engine, raw_table, all_objects)
    print(f"  {raw_table}: {len(all_objects)} rows (full_reload, bare)")


async def _replace_table(engine, raw_table: str, objects: list[dict]):
    """DELETE + INSERT all objects (an empty answer clears the table)."""
    if not objects:
        async with engine.begin() as conn:
            await conn.execute(text(f'DELETE FROM "{raw_table}"'))
        return

    async with engine.begin() as conn:
        # Get api_field → db_column mapping for this endpoint
        ep_r = await conn.execute(
            text("SELECT endpoint_name FROM meta_endpoint WHERE raw_table = :t"),
            {"t": raw_table},
        )
        ep_row = ep_r.fetchone()
        if not ep_row:
            return
        ep_name = ep_row[0]

        r = await conn.execute(
            text("""
            SELECT api_field, db_column FROM meta_field_mapping
            WHERE endpoint_name = :ep AND is_loaded = True
        """),
            {"ep": ep_name},
        )
        mapping = {row[0]: row[1] for row in r}

        if not mapping:
            # fallback: use api fields as-is
            sample = objects[0]
            mapping = {k: k for k in sample}
        # Build INSERT columns: all mapped db_columns minus serial PK + _raw_json
        all_db_cols = set(v for v in mapping.values())

        # Check which db columns are serial PKs
        pk_r = await conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND table_schema = current_schema()
            AND column_default LIKE 'nextval(%'
        """),
            {"t": raw_table},
        )
        serial_pks = {row[0] for row in pk_r}

        col_names = [c for c in all_db_cols if c not in serial_pks] + ["_raw_json"]
        if not col_names:
            return
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_str = ", ".join(f'"{c}"' for c in col_names)
        insert_sql = f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders})'

        # DELETE, как в app raw_sync: TRUNCATE ... CASCADE мог утащить
        # зависимые raw-таблицы, а внутри транзакции его нельзя безопасно
        # откатить в fallback.
        await conn.execute(text(f'DELETE FROM "{raw_table}"'))

        for obj in objects:
            raw_json = json.dumps(obj, ensure_ascii=False)
            values = {}
            for c in col_names:
                if c == "_raw_json":
                    values[c] = raw_json
                    continue
                # Find the api_field for this db_column
                api_field = next((k for k, v in mapping.items() if v == c), c)
                val = obj.get(api_field)
                if val is not None and isinstance(val, (dict, list)):
                    values[c] = json.dumps(val, ensure_ascii=False)
                elif val is not None:
                    values[c] = str(val)
                else:
                    values[c] = None
            await conn.execute(text(insert_sql), values)


async def sync_incremental_page(engine, token, endpoint: dict, raw_table: str, api_path: str):
    """Incremental sync by page number (submissions, attempts).
    Tracks step_id → last_page in raw_sync_state."""
    clean = clean_path(api_path)
    step_ids = await get_step_ids(engine)
    if not step_ids:
        print(f"  {raw_table}: no steps")
        return

    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT key, value FROM raw_sync_state WHERE endpoint_name = :ep AND key LIKE 'step_%'"),
            {"ep": endpoint["endpoint_name"]},
        )
        state = {int(row[0].split("_", 1)[1]): int(row[1]) for row in r}

    total_new = 0
    max_pages_per_step = 500

    for sid in step_ids:
        last_page = state.get(int(sid), 0)
        # Продолжаем С последней страницы: новые записи заполняют хвост
        # последней скачанной страницы (API oldest-first); upsert дедуплит повторы
        page = last_page if last_page > 0 else 1
        step_new = 0

        while page <= max_pages_per_step:
            try:
                data = await fetch_page(clean, token, {"step": sid, "page": page})
            except StepikAPIError as e:
                # 404 — шаг удалён, 400 — теоретический шаг без решений.
                if e.status_code in (400, 404):
                    print(f"    step {sid}: {e.status_code} — skip")
                    break
                raise
            objects = extract_objects(data, api_path)
            if not objects:
                break

            # API не возвращает step в объекте submission — шаг известен
            # только из контекста запроса ?step=; пишем его в колонку step
            for obj in objects:
                obj["step"] = sid

            await _upsert_objects(engine, raw_table, api_path, objects, extra_columns={"step": str(sid)})
            step_new += len(objects)
            total_new += len(objects)

            meta = data.get("meta", {})
            has_next = meta.get("has_next", False)

            # Update state after each page
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO raw_sync_state (endpoint_name, key, value) "
                        "VALUES (:ep, :k, :v) "
                        "ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"
                    ),
                    {"ep": endpoint["endpoint_name"], "k": f"step_{sid}", "v": str(page), "v2": str(page)},
                )

            if not has_next:
                break
            page += 1
            await asyncio.sleep(0.3)

        if step_new > 0:
            print(f"    step {sid}: +{step_new} (page {last_page + 1}→{page})")

    print(f"  {raw_table}: +{total_new} rows (incremental_page, steps)")

    # Second pass: fetch author submissions via ?course=X (real user field)
    ep_name = endpoint["endpoint_name"]
    if ep_name in STEP_COURSE_ENDPOINTS:
        print(f"  {raw_table}: fetching author submissions per-course...")
        course_ids = await get_course_ids(engine)

        # Инкрементальные страницы по курсам (как в raw_sync.sync_submissions):
        # раньше каждый запуск начинал с page=1 и падал на втором запуске —
        # INSERT без ON CONFLICT задевал уникальность submission_id
        async with engine.begin() as conn:
            r = await conn.execute(
                text("SELECT key, value FROM raw_sync_state WHERE endpoint_name = :ep AND key LIKE 'course_%'"),
                {"ep": ep_name},
            )
            course_state = {int(row[0].split("_", 1)[1]): int(row[1]) for row in r}

        author_total = 0
        for cid in course_ids:
            last_page = course_state.get(int(cid), 0)
            page = last_page if last_page > 0 else 1
            while page <= 500:
                try:
                    data = await fetch_page(clean, token, {"course": cid, "page": page})
                except StepikAPIError as e:
                    if e.status_code == 404:
                        print(f"    course {cid}: 404 — skip")
                        break
                    raise
                objects = extract_objects(data, api_path)
                if not objects:
                    break
                await _upsert_objects(engine, raw_table, api_path, objects)
                author_total += len(objects)
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO raw_sync_state (endpoint_name, key, value) "
                            "VALUES (:ep, :k, :v) "
                            "ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"
                        ),
                        {"ep": ep_name, "k": f"course_{cid}", "v": str(page), "v2": str(page)},
                    )
                meta = data.get("meta", {})
                if not meta.get("has_next"):
                    break
                page += 1
                await asyncio.sleep(0.3)
            if author_total > 0:
                print(f"    course {cid}: +{author_total} author submissions so far")
        print(f"  {raw_table}: +{author_total} rows (incremental_page, courses->author_submissions)")


async def sync_incremental_time(engine, token, endpoint: dict, raw_table: str, api_path: str):
    """Incremental sync by time field (comments).
    Reads last sync time from raw_sync_state, appends newer records."""
    clean = clean_path(api_path)
    ep_name = endpoint["endpoint_name"]
    course_ids = await get_course_ids(engine)
    if not course_ids:
        print(f"  {raw_table}: no courses")
        return

    # Read last sync time per course
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT key, value FROM raw_sync_state WHERE endpoint_name = :ep AND key LIKE 'last_time_course_%'"),
            {"ep": ep_name},
        )
        last_times = {row[0]: row[1] for row in r}

    total_new = 0
    for cid in course_ids:
        last_time = last_times.get(f"last_time_course_{cid}", "")
        last_dt = _parse_time(last_time)
        course_new = 0
        page = 1
        max_time_str = last_time
        max_dt = last_dt
        reached_boundary = False

        while page <= 500:
            try:
                data = await fetch_page(clean, token, {"course": cid, "page": page})
            except StepikAPIError as e:
                if e.status_code in (400, 404):
                    print(f"    course {cid}: {e.status_code} — skip")
                    break
                raise
            objects = extract_objects(data, api_path)
            if not objects:
                reached_boundary = True
                break

            # `>=` (not `>`): не теряем комментарии, созданные в ту же
            # секунду, что и сохранённый курсор.
            new_objects = []
            for obj in objects:
                t = obj.get("time", "") or ""
                if not isinstance(t, str):
                    continue
                t_dt = _parse_time(t)
                is_old = (t_dt < last_dt) if (t_dt is not None and last_dt is not None) else bool(
                    last_time and t < last_time
                )
                if is_old:
                    reached_boundary = True
                if not is_old:
                    new_objects.append(obj)
                    newer = (t_dt > max_dt) if (t_dt is not None and max_dt is not None) else t > max_time_str
                    if newer:
                        max_dt = t_dt
                        max_time_str = t

            if new_objects:
                await _upsert_objects(engine, raw_table, api_path, new_objects)
                course_new += len(new_objects)

            if reached_boundary:
                break
            if not data.get("meta", {}).get("has_next"):
                reached_boundary = True
                break
            page += 1
            await asyncio.sleep(0.3)

        if course_new > 0:
            if reached_boundary:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO raw_sync_state (endpoint_name, key, value) "
                            "VALUES (:ep, :k, :v) "
                            "ON CONFLICT (endpoint_name, key) DO UPDATE SET value = :v2"
                        ),
                        {"ep": ep_name, "k": f"last_time_course_{cid}", "v": max_time_str, "v2": max_time_str},
                    )
            else:
                print(f"    500-page backlog not fully fetched for course {cid}; cursor kept")
            print(f"    course {cid}: +{course_new} (last_time={last_time})")
        total_new += course_new

    print(f"  {raw_table}: +{total_new} rows (incremental_time)")


async def _upsert_objects(
    engine, raw_table: str, api_path: str, objects: list[dict], extra_columns: dict | None = None
):
    """INSERT objects for incremental sync.

    ON CONFLICT DO UPDATE (not DO NOTHING): повторная загрузка последней
    страницы не должна ронять скрипт на unique-констрейнтах, но обязана
    обновлять изменяемые объекты (комментарии: текст, лайки, ответы).
    Контекстные extra_columns (step для submissions) не затираются пустым
    значением — COALESCE сохраняет уже записанный шаг."""
    if not objects:
        return
    sample = objects[0]

    async with engine.begin() as conn:
        ep_r = await conn.execute(
            text("SELECT endpoint_name FROM meta_endpoint WHERE raw_table = :t"),
            {"t": raw_table},
        )
        ep_row = ep_r.fetchone()
        if not ep_row:
            return
        ep_name = ep_row[0]

        r = await conn.execute(
            text("""
            SELECT api_field, db_column FROM meta_field_mapping
            WHERE endpoint_name = :ep AND is_loaded = True
        """),
            {"ep": ep_name},
        )
        mapping = {row[0]: row[1] for row in r}

        if not mapping:
            mapping = {k: k for k in sample}

        all_db_cols = set(v for v in mapping.values())
        if extra_columns:
            all_db_cols |= set(extra_columns)
        pk_r = await conn.execute(
            text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :t AND table_schema = current_schema()
            AND column_default LIKE 'nextval(%'
        """),
            {"t": raw_table},
        )
        serial_pks = {row[0] for row in pk_r}

        col_names = [c for c in dict.fromkeys(all_db_cols) if c not in serial_pks]
        if "_raw_json" not in col_names:
            col_names.append("_raw_json")
        placeholders = ", ".join(f":{c}" for c in col_names)
        cols_str = ", ".join(f'"{c}"' for c in col_names)

        id_field = _NATURAL_KEYS.get(raw_table) or next(
            (c for c in col_names if c.endswith("_id")), None
        )
        conflict = ""
        if id_field:
            assignments = []
            for col in col_names:
                if col == id_field:
                    continue
                if extra_columns and col in extra_columns:
                    assignments.append(f'"{col}" = COALESCE(EXCLUDED."{col}", "{raw_table}"."{col}")')
                else:
                    assignments.append(f'"{col}" = EXCLUDED."{col}"')
            if assignments:
                conflict = f' ON CONFLICT ("{id_field}") DO UPDATE SET {", ".join(assignments)}'
        insert_sql = f'INSERT INTO "{raw_table}" ({cols_str}) VALUES ({placeholders}){conflict}'

        for obj in objects:
            raw_json = json.dumps(obj, ensure_ascii=False)
            values = {}
            for c in col_names:
                if c == "_raw_json":
                    values[c] = raw_json
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
            await conn.execute(text(insert_sql), values)


async def main():
    parser = argparse.ArgumentParser(description="Sync raw tables from Stepik API")
    parser.add_argument("endpoints", nargs="*", help="Endpoint names to sync (default: all active)")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        if args.endpoints:
            r = await conn.execute(
                text(
                    "SELECT * FROM meta_endpoint "
                    "WHERE endpoint_name = ANY(:names) AND is_active = True ORDER BY endpoint_name"
                ),
                {"names": args.endpoints},
            )
        else:
            r = await conn.execute(text("SELECT * FROM meta_endpoint WHERE is_active = True ORDER BY endpoint_name"))
        endpoints = [dict(row._mapping) for row in r]

    if not endpoints:
        print("No active endpoints to sync")
        await engine.dispose()
        return

    print(f"Syncing {len(endpoints)} endpoints...\n")

    user_token = None
    client_token = None

    for ep in endpoints:
        ep_name = ep["endpoint_name"]
        strategy = ep["incremental"]
        api_path = ep["api_path"]
        raw_table = ep["raw_table"]
        auth_method = ep["auth_method"]

        print(f"[{ep_name}] {raw_table} ({strategy})")

        # Get token
        token = None
        if auth_method == "client_credentials":
            if not client_token:
                client_token = await get_client_token()
            token = client_token
        else:
            if not user_token:
                user_token = await get_user_token()
            token = user_token

        if not token:
            print("  SKIP: no token")
            continue

        try:
            if strategy == "full_reload":
                await sync_full_reload(engine, token, ep, raw_table, api_path)
            elif strategy == "incremental_page":
                await sync_incremental_page(engine, token, ep, raw_table, api_path)
            elif strategy == "incremental_time":
                await sync_incremental_time(engine, token, ep, raw_table, api_path)
            else:
                print(f"  SKIP: unknown strategy '{strategy}'")
        except Exception as e:
            import traceback

            print(f"  ERROR: {e}")
            traceback.print_exc()

        print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
