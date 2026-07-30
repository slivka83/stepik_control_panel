"""
Full data load for an endpoint: read IDs from source raw table, fetch ALL from API, upsert.

Usage: python scripts/full_load.py <endpoint_name>

Examples:
    python scripts/full_load.py units      # load units (IDs from raw_section.unit_ids)
    python scripts/full_load.py lessons    # load lessons (IDs from raw_unit.lesson_id)
    python scripts/full_load.py steps      # load steps (IDs from raw_lesson.step_ids)
"""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.services.crypto import decrypt_token
from app.services.stepik_api import STEPIK_API_BASE

s = get_settings()
engine = create_async_engine(s.database_url)

# Source: how to get IDs for each endpoint
ID_SOURCES = {
    "units": ("raw_section", "units"),         # raw_section.units → JSONB array
    "lessons": ("raw_unit", "lesson_id"),       # raw_unit.lesson_id → single value
    "steps": ("raw_lesson", "steps"),           # raw_lesson.steps → JSONB array
}

# For endpoints that need ?course= param
COURSE_SOURCES = {
    "course_grades": "raw_course",
    "certificates": "raw_course",
    "comments": "raw_course",
    "course_reviews": "raw_course",
    "enrollments": "raw_course",
}


async def get_ids(endpoint_name: str) -> list[str]:
    """Collect IDs to fetch from the API."""
    src = ID_SOURCES.get(endpoint_name)
    if src:
        table, column = src
        async with engine.begin() as conn:
            r = await conn.execute(text(f'SELECT "{column}" FROM "{table}"'))
            seen = set()
            ids = []
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
                    if sid not in seen:
                        seen.add(sid)
                        ids.append(sid)
            return ids

    if endpoint_name in COURSE_SOURCES:
        table = COURSE_SOURCES[endpoint_name]
        async with engine.begin() as conn:
            r = await conn.execute(text(f'SELECT course_id FROM "{table}" ORDER BY course_id'))
            return [str(row[0]) for row in r if row[0] is not None]

    return []


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/full_load.py <endpoint_name>")
        return
    ep_name = sys.argv[1]

    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT raw_table, api_path, auth_method FROM meta_endpoint WHERE endpoint_name = :en"),
            {"en": ep_name},
        )
        ep = r.fetchone()
        if not ep:
            print(f"Endpoint '{ep_name}' not found")
            return
        raw_table, api_path, auth_method = ep

    # Get IDs
    ids = await get_ids(ep_name)
    if not ids:
        print("No IDs to fetch")
        return
    print(f"IDs to fetch: {len(ids)}")

    # Token
    token_enc = None
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT access_token FROM users ORDER BY created_at DESC LIMIT 1"))
        token_enc = r.scalar()
    if not token_enc:
        print("No token in DB")
        return
    token = decrypt_token(token_enc)

    # Get mapping: api_field → db_column for the raw table
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT api_field, db_column FROM meta_field_mapping WHERE endpoint_name = :en AND is_loaded = true"),
            {"en": ep_name},
        )
        mapping = [(row[0], row[1]) for row in r.fetchall()]
    if not mapping:
        print("No loaded fields in meta — run rebuild_raw.py first")
        return

    print(f"Fields to load: {len(mapping)}")

    # Fetch from API
    # Strip /api prefix (STEPIK_API_BASE already has it) and query params
    path = api_path.split("?")[0]
    if path.startswith("/api/"):
        path = path[4:]  # /api/courses → /courses
    elif path.startswith("api/"):
        path = "/" + path[4:]
    params = {}
    if ep_name in COURSE_SOURCES:
        params["course"] = ids[0]  # one course at a time
    elif ep_name in ID_SOURCES:
        params["ids[]"] = ids  # batch all IDs

    url = f"{STEPIK_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    all_objects = []
    page = 1
    max_pages = 20

    async with httpx.AsyncClient(timeout=30.0) as client:
        while page <= max_pages:
            page_params = {**params, "page": page}
            resp = await client.get(url, headers=headers, params=page_params)
            if resp.status_code >= 400:
                print(f"  HTTP {resp.status_code} on page {page}: {resp.text[:200]}")
                break
            data = resp.json()
            objects = data.get(ep_name, [])
            if not objects:
                break
            all_objects.extend(objects)
            meta = data.get("meta", {})
            if not meta.get("has_next"):
                break
            page += 1

    print(f"Fetched {len(all_objects)} records from API")

    if not all_objects:
        return

    # Truncate and reload
    async with engine.begin() as conn:
        await conn.execute(text(f'TRUNCATE "{raw_table}" RESTART IDENTITY CASCADE'))

        col_names = [f'"{db_c}"' for _, db_c in mapping] + ['"_raw_json"']
        ph = ", ".join(f":p{i}" for i in range(len(col_names)))
        sql = f'INSERT INTO "{raw_table}" ({", ".join(col_names)}) VALUES ({ph})'

        loaded = 0
        for obj in all_objects:
            raw_json = json.dumps(obj, ensure_ascii=False)
            values = []
            for af, _ in mapping:
                val = obj.get(af)
                if val is not None and isinstance(val, (dict, list)):
                    values.append(json.dumps(val, ensure_ascii=False))
                elif val is not None:
                    values.append(str(val))
                else:
                    values.append(None)
            prm = {f"p{i}": values[i] for i in range(len(values))}
            prm[f"p{len(values)}"] = raw_json
            await conn.execute(text(sql), prm)
            loaded += 1

        cnt = await conn.execute(text(f'SELECT COUNT(*) FROM "{raw_table}"'))
        print(f"Loaded {loaded}. Total rows: {cnt.scalar()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
