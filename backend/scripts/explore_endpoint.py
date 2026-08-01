"""
Explore a Stepik API endpoint: fetch one page, compare fields with meta mapping,
optionally create raw table and load data.

Usage:
    python scripts/explore_endpoint.py <endpoint_name> [--create-table] [--load]
    python scripts/explore_endpoint.py <endpoint_name> --create-table --load [--ids ID [ID ...]]

Examples:
    python scripts/explore_endpoint.py courses
    python scripts/explore_endpoint.py courses --create-table
    python scripts/explore_endpoint.py courses --create-table --load
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.crypto import decrypt_token
from app.services.stepik_api import STEPIK_API_BASE, STEPIK_OAUTH_TOKEN_URL

settings = get_settings()

# Mapping: endpoint_name → (source_raw_table, source_db_column) for ?ids[]= resolution.
# source_db_column is the actual column name in the source raw table (from meta_field_mapping.db_column).
# Use "__multi__" as table name for endpoints that aggregate IDs from multiple sources.
IDS_SOURCE_MAP = {
    "sections": ("raw_course", "section_ids"),
    "units": ("raw_section", "units"),
    "lessons": ("raw_unit", "lesson_id"),  # raw_unit.lesson_id holds single lesson ID
    "steps": ("raw_lesson", "steps"),  # raw_lesson.steps is JSONB array
    "course_review_summaries": ("raw_course", "review_summary_json"),
    "progresses": ("raw_step", "progress"),
    "users": ("__multi__", "user"),
    "profiles": ("raw_user", "profile"),
}
# Endpoints that need a specific step_id (?step=X param)
STEP_ENDPOINTS = {"attempts", "submissions"}
# Endpoints that need a course_id (?course=X param)
COURSE_ENDPOINTS = {
    "course_grades",
    "certificates",
    "comments",
    "course_reviews",
    "enrollments",
    "course_period_statistics",
    "course_total_statistics",
    "course_ranks",
}


async def get_user_token() -> str | None:
    """Get decrypted user token from DB."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT access_token FROM users ORDER BY created_at DESC LIMIT 1"))
        row = r.fetchone()
    await engine.dispose()
    if row:
        return decrypt_token(row[0])
    return None


async def get_client_token() -> str | None:
    """Get client_credentials token."""
    if settings.stepik_finance_client_id:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                STEPIK_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.stepik_finance_client_id,
                    "client_secret": settings.stepik_finance_client_secret,
                    "scope": "read",
                },
                timeout=30.0,
            )
            if resp.status_code < 400:
                data = resp.json()
                return data.get("access_token")
    # Fallback: try with regular client_id
    if settings.stepik_client_id:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                STEPIK_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.stepik_client_id,
                    "client_secret": settings.stepik_client_secret,
                    "scope": "read",
                },
                timeout=30.0,
            )
            if resp.status_code < 400:
                data = resp.json()
                return data.get("access_token")
    return None


def extract_api_name(path: str) -> str:
    """/api/courses → courses, /api/course-grades?course=X → course_grades"""
    m = re.search(r"/api/([a-z][a-z0-9-]*)", path)
    if m:
        return m.group(1).replace("-", "_")
    return "unknown"


def describe_value(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        if len(val) > 100:
            return "text(truncated)"
        return "text"
    if isinstance(val, list):
        if val and isinstance(val[0], dict):
            return f"array<object>(len={len(val)})"
        return f"array(len={len(val)})"
    if isinstance(val, dict):
        return f"object({len(val)} keys)"
    return type(val).__name__


DB_TYPE_MAP_SCRIPT = {
    "integer": "integer",
    "float": "numeric",
    "boolean": "boolean",
    "text": "text",
    "text(truncated)": "text",
    "null": "text",
}


def guess_db_type(val) -> str:
    desc = describe_value(val)
    if desc.startswith("array") or desc.startswith("object"):
        return "jsonb"
    if desc.startswith("text"):
        return "text"
    if desc in DB_TYPE_MAP_SCRIPT:
        return DB_TYPE_MAP_SCRIPT[desc]
    return "text"


async def resolve_ids_for_endpoint(engine, endpoint_name: str, limit: int | None = 5) -> list[str]:
    """Resolve IDs for ?ids[]= endpoints from existing raw tables."""
    src = IDS_SOURCE_MAP.get(endpoint_name)
    if not src:
        return []

    raw_table, field = src

    # Multi-source: aggregate user IDs from various raw tables
    if raw_table == "__multi__":
        queries = {
            "user": [
                "SELECT DISTINCT user_id FROM raw_course_grade WHERE user_id IS NOT NULL",
                "SELECT DISTINCT user FROM raw_comment WHERE user IS NOT NULL",
                "SELECT DISTINCT user_id FROM raw_certificate WHERE user_id IS NOT NULL",
                "SELECT DISTINCT user FROM raw_course_review WHERE user IS NOT NULL",
            ],
        }
        sql_queries = queries.get(field, [])
        seen = set()
        ids = []
        async with engine.begin() as conn:
            for q in sql_queries:
                try:
                    r = await conn.execute(text(q))
                    for row in r:
                        sid = str(row[0])
                        if not sid.lstrip("-").isdigit():
                            continue  # skip non-numeric IDs
                        if sid not in seen:
                            seen.add(sid)
                            ids.append(sid)
                            if limit is not None and len(ids) >= limit:
                                break
                except Exception:
                    continue
                if limit is not None and len(ids) >= limit:
                    break
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
                    if limit is not None and len(ids) >= limit:
                        break
            if limit is not None and len(ids) >= limit:
                break

    return ids


async def get_course_ids(engine, limit: int = 1) -> list[str]:
    """Get course IDs from raw_course."""
    async with engine.begin() as conn:
        r = await conn.execute(text(f"SELECT course_id FROM raw_course ORDER BY course_id LIMIT {limit}"))
        return [str(row[0]) for row in r if row[0] is not None]


async def get_step_ids(engine, limit: int = 1) -> list[str]:
    """Get step IDs from raw_step (for ?step=X endpoints)."""
    async with engine.begin() as conn:
        r = await conn.execute(text(f"SELECT step_id FROM raw_step ORDER BY step_id LIMIT {limit}"))
        return [str(row[0]) for row in r if row[0] is not None]


async def resolve_params(engine, api_path: str, endpoint_name: str) -> dict | None:
    """Build query params for the API call, resolving IDs from DB when needed."""
    params = {}

    if "?teacher=" in api_path and settings.stepik_user_id:
        params["teacher"] = settings.stepik_user_id

    if "?course=X" in api_path or "?course=" in api_path:
        ids = await get_course_ids(engine, limit=1)
        if ids:
            params["course"] = ids[0]

    if "?ids[]=" in api_path:
        if "/stepics/" in api_path:
            return None
        ids = await resolve_ids_for_endpoint(engine, endpoint_name, limit=3)
        if ids:
            params["ids[]"] = ids

    # Endpoints needing ?step=X but without ? in api_path
    if endpoint_name in STEP_ENDPOINTS:
        ids = await get_step_ids(engine, limit=1)
        if ids:
            params["step"] = ids[0]

    # Endpoints needing ?course=X but without ? in api_path
    if endpoint_name in COURSE_ENDPOINTS:
        ids = await get_course_ids(engine, limit=1)
        if ids:
            params["course"] = ids[0]

    return params if params else None


def clean_path(api_path: str) -> str:
    """Extract just the endpoint path without /api prefix or query params."""
    # Handle /api/stepics/1 → /stepics/1
    if "/stepics/" in api_path:
        m = re.search(r"/api/(stepics/\d+)", api_path)
        if m:
            return "/" + m.group(1)
    # Handle /api/courses?ids[]= → /courses
    m = re.search(r"/api/([a-z][a-z0-9-]*)", api_path)
    if m:
        return "/" + m.group(1)
    return api_path


async def fetch_page(path: str, token: str, params: dict | None = None) -> dict:
    """Fetch one page from Stepik API. Path should be like /courses (without /api)."""
    url = f"{STEPIK_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code >= 400:
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
        return resp.json()


def compare_fields(api_obj: dict, endpoint_name: str, mapping_rows: list[dict]) -> list[dict]:
    """Compare API response fields with meta_field_mapping."""
    if not api_obj:
        return []

    results = []
    api_keys = set(api_obj.keys())
    mapped_keys = {r["api_field"] for r in mapping_rows}

    # Fields in API but not in mapping
    for key in sorted(api_keys - mapped_keys):
        results.append(
            {
                "api_field": key,
                "db_column": key,
                "db_type": guess_db_type(api_obj[key]),
                "status": "NEW",
                "note": f"value={describe_value(api_obj[key])}",
            }
        )

    # Fields in mapping but not in API
    for key in sorted(mapped_keys - api_keys):
        results.append(
            {
                "api_field": key,
                "db_column": next(r["db_column"] for r in mapping_rows if r["api_field"] == key),
                "db_type": next(r["db_type"] for r in mapping_rows if r["api_field"] == key),
                "status": "MISSING",
                "note": "not in API response",
            }
        )

    # Fields that match
    for key in sorted(api_keys & mapped_keys):
        mr = next(r for r in mapping_rows if r["api_field"] == key)
        api_val = api_obj[key]
        guessed_type = guess_db_type(api_val)
        mapped_type = mr["db_type"]

        status = "OK"
        note = ""
        if guessed_type != mapped_type:
            if mapped_type == "jsonb" and guessed_type != "jsonb":
                status = "OK"
            else:
                status = "TYPE_MISMATCH"
                note = f"mapped={mapped_type} actual={guessed_type}"

        results.append(
            {
                "api_field": key,
                "db_column": mr["db_column"],
                "db_type": guessed_type,
                "mapped_type": mapped_type if status == "TYPE_MISMATCH" else "",
                "is_loaded": mr["is_loaded"],
                "status": status,
                "note": note,
            }
        )

    return results


async def create_raw_table(engine, raw_table: str, fields: list[dict]) -> None:
    """CREATE TABLE IF NOT EXISTS for the raw table.
    Scalar fields are stored as text (raw strings from API).
    Arrays/objects are stored as jsonb.
    """
    col_defs = ['"id" SERIAL PRIMARY KEY']
    for f in fields:
        if f["status"] == "MISSING":
            continue
        if f["db_column"] == "id":
            continue  # already have serial PK
        col_type = f["db_type"]
        is_json = col_type == "jsonb" or col_type.startswith("array") or col_type.startswith("object")
        if is_json:
            col_defs.append(f'"{f["db_column"]}" jsonb')
        else:
            col_defs.append(f'"{f["db_column"]}" text')

    col_defs.append('"_raw_json" jsonb')
    col_defs.append('"_loaded_at" timestamptz DEFAULT now()')

    sql = f'CREATE TABLE IF NOT EXISTS "{raw_table}" (\n  ' + ",\n  ".join(col_defs) + "\n);"
    async with engine.begin() as conn:
        await conn.execute(text(sql))
    print(f"  Table '{raw_table}' created/verified.")


async def get_api_object_name(api_path: str, data: dict) -> str | None:
    """Determine the API object name from response."""
    # The response key is usually the last part of endpoint name (plural)
    # e.g., {'courses': [...]}
    for key in data:
        if isinstance(data[key], list) and key != "meta":
            return key
    return None


def extract_objects(data: dict) -> list[dict]:
    """Extract the list of objects from API response."""
    for key, val in data.items():
        if isinstance(val, list) and key != "meta":
            return val
    return []


async def load_data(
    engine, raw_table: str, path: str, token: str, api_path: str, params: dict | None, fields: list[dict]
) -> int:
    """Load paginated data into the raw table. Returns total records loaded."""
    total = 0
    page = 1
    max_pages = 1  # Just one page for exploration

    ep_name = extract_api_name(api_path)
    loaded_fields = [f for f in fields if f["status"] != "MISSING" and f["db_column"] != "id"]

    # For ?ids[]= endpoints: batch by 100 IDs to avoid URI Too Long
    if params and "ids[]" in params:
        full_ids = await resolve_ids_for_endpoint(engine, ep_name, limit=None)
        if not full_ids:
            return 0
        batch_size = 100
        for batch_start in range(0, len(full_ids), batch_size):
            batch = full_ids[batch_start : batch_start + batch_size]
            batch_params = {"ids[]": batch}
            data = await fetch_page(path, token, batch_params)
            objects = extract_objects(data)
            if not objects:
                continue
            await _insert_objects(engine, raw_table, objects, loaded_fields)
            total += len(objects)
            print(f"  ... {total} records loaded so far")
            await asyncio.sleep(0.3)  # rate limit buffer
        return total

    while page <= max_pages:
        page_params = dict(params) if params else {}
        page_params["page"] = page

        try:
            data = await fetch_page(path, token, page_params)
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

        objects = extract_objects(data)
        if not objects:
            break

        await _insert_objects(engine, raw_table, objects, loaded_fields)

        total += len(objects)
        meta = data.get("meta", {})
        has_next = meta.get("has_next", False)
        if not has_next:
            break
        page += 1
        max_pages = 5  # Allow more pages during loading phase

    return total


async def _insert_objects(engine, raw_table: str, objects: list[dict], loaded_fields: list[dict]):
    """Insert a batch of objects into the raw table."""
    col_names = [f["db_column"] for f in loaded_fields] + ["_raw_json"]
    placeholders = ", ".join(f":{c}" for c in col_names)
    cols = ", ".join(f'"{c}"' for c in col_names)
    insert_sql = f'INSERT INTO "{raw_table}" ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    async with engine.begin() as conn:
        for obj in objects:
            raw_json = json.dumps(obj, ensure_ascii=False)
            values = []
            for f in loaded_fields:
                val = obj.get(f["api_field"])
                if val is not None and isinstance(val, (dict, list)):
                    values.append(json.dumps(val, ensure_ascii=False))
                elif val is not None:
                    values.append(str(val))
                else:
                    values.append(None)

            param_dict = dict(zip(col_names, values + [raw_json], strict=False))
            await conn.execute(text(insert_sql), param_dict)


async def main():
    parser = argparse.ArgumentParser(description="Explore a Stepik API endpoint")
    parser.add_argument("endpoint_name", help="Endpoint name from meta_endpoint")
    parser.add_argument("--create-table", action="store_true", help="Create raw table")
    parser.add_argument("--load", action="store_true", help="Load data into raw table")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url)

    # Read endpoint info from meta
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT * FROM meta_endpoint WHERE endpoint_name = :en"),
            {"en": args.endpoint_name},
        )
        endpoint = r.fetchone()
        if not endpoint:
            print(f"Endpoint '{args.endpoint_name}' not found in meta_endpoint")
            await engine.dispose()
            return

        r = await conn.execute(
            text(
                "SELECT api_field, db_column, db_type, is_loaded, skip_reason "
                "FROM meta_field_mapping WHERE endpoint_name = :en ORDER BY id"
            ),
            {"en": args.endpoint_name},
        )
        mapping = [dict(r._mapping) for r in r.fetchall()]

    ep = dict(endpoint._mapping)
    ep_name = ep["endpoint_name"]
    api_path = ep["api_path"]
    auth_method = ep["auth_method"]
    raw_table = ep["raw_table"]
    is_active = ep["is_active"]

    print(f"=== {ep_name} ===")
    print(f"  Path: {api_path}")
    print(f"  Auth: {auth_method}")
    print(f"  Raw table: {raw_table}")
    print(f"  Active: {is_active}")
    print(f"  Mapped fields: {len(mapping)}")

    if not is_active:
        print("  SKIPPED: endpoint not active")
        await engine.dispose()
        return

    # Get token
    token = None
    if auth_method == "client_credentials":
        print("  Getting client_credentials token...")
        token = await get_client_token()
    else:
        print("  Getting user token from DB...")
        token = await get_user_token()

    if not token:
        print("  ERROR: could not get auth token")
        await engine.dispose()
        return

    # Determine API path and params
    clean_api_path = clean_path(api_path)
    params = await resolve_params(engine, api_path, ep_name)

    print(f"  Clean path: {clean_api_path}")
    if params:
        print(f"  Params: {params}")
    else:
        print("  No params resolved — trying bare endpoint")

    # Fetch one page
    print("  Fetching API...")
    try:
        data = await fetch_page(clean_api_path, token, params)
    except Exception as e:
        print(f"  ERROR: {e}")
        await engine.dispose()
        return

    api_obj_name = await get_api_object_name(api_path, data)
    objects = extract_objects(data)

    if not objects:
        print("  Empty response. Sample keys:", list(data.keys()))
        await engine.dispose()
        return

    sample = objects[0]
    print(f"  Object: {api_obj_name}")
    print(f"  Records: {len(objects)}")
    print(f"  API fields: {len(sample)}")

    # Compare fields
    comparison = compare_fields(sample, ep_name, mapping)

    new_fields = [f for f in comparison if f["status"] == "NEW"]
    missing_fields = [f for f in comparison if f["status"] == "MISSING"]
    type_mismatches = [f for f in comparison if f["status"] == "TYPE_MISMATCH"]
    ok_fields = [f for f in comparison if f["status"] == "OK"]

    print()
    print(
        f"  Comparison: {len(ok_fields)} OK, {len(new_fields)} NEW, "
        f"{len(missing_fields)} MISSING, {len(type_mismatches)} TYPE_MISMATCH"
    )

    if new_fields:
        print("\n  --- NEW FIELDS (in API but not in mapping) ---")
        for f in new_fields:
            print(f"    + {f['api_field']:30s} → {f['db_column']:30s} ({f['db_type']})")

    if missing_fields:
        print("\n  --- MISSING FIELDS (in mapping but not in API) ---")
        for f in missing_fields:
            print(f"    - {f['api_field']:30s} (skipped: {f.get('note', '')})")

    if type_mismatches:
        print("\n  --- TYPE MISMATCHES ---")
        for f in type_mismatches:
            print(f"    ~ {f['api_field']:30s} mapped={f['mapped_type']:15s} actual={f['db_type']}")

    # Print sample data for new fields
    if new_fields:
        print("\n  --- Sample values for new fields ---")
        for f in new_fields[:5]:
            val = sample.get(f["api_field"])
            print(f"    {f['api_field']} = {json.dumps(val, ensure_ascii=False, default=str)[:200]}")

    # Create table
    if args.create_table:
        print("\n  Creating raw table...")
        all_fields = comparison
        await create_raw_table(engine, raw_table, all_fields)

    # Load data
    if args.load and args.create_table:
        print("\n  Loading data...")
        # For loading, get more IDs
        load_params = await resolve_params(engine, api_path, ep_name)
        total = await load_data(engine, raw_table, clean_api_path, token, api_path, load_params, comparison)
        print(f"  Loaded {total} records into {raw_table}")

    # Update meta_field_mapping if --create-table was used
    if args.create_table:
        await update_meta_mapping(engine, ep_name, comparison)

    await engine.dispose()


async def update_meta_mapping(engine, endpoint_name: str, fields: list[dict]):
    """Update meta_field_mapping with discovered fields."""
    async with engine.begin() as conn:
        for f in fields:
            if f["status"] == "OK":
                continue  # Already in mapping

            api_field = f["api_field"]
            db_column = f["db_column"]
            db_type = f["db_type"]

            if f["status"] == "NEW":
                # Insert new field
                await conn.execute(
                    text("""
                        INSERT INTO meta_field_mapping (endpoint_name, api_field, db_column, db_type, is_loaded)
                        VALUES (:en, :af, :dc, :dt, false)
                        ON CONFLICT (endpoint_name, api_field) DO UPDATE
                        SET db_column = EXCLUDED.db_column, db_type = EXCLUDED.db_type
                    """),
                    {"en": endpoint_name, "af": api_field, "dc": db_column, "dt": db_type},
                )
            elif f["status"] == "MISSING":
                # Mark as not loaded
                await conn.execute(
                    text("""
                        UPDATE meta_field_mapping
                        SET is_loaded = false, skip_reason = 'not in API response'
                        WHERE endpoint_name = :en AND api_field = :af
                    """),
                    {"en": endpoint_name, "af": api_field},
                )
            elif f["status"] == "TYPE_MISMATCH":
                # Update type
                await conn.execute(
                    text("""
                        UPDATE meta_field_mapping
                        SET db_type = :dt
                        WHERE endpoint_name = :en AND api_field = :af
                    """),
                    {"en": endpoint_name, "af": api_field, "dt": db_type},
                )

        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM meta_field_mapping WHERE endpoint_name = :en"),
                {"en": endpoint_name},
            )
        ).scalar()
        print(f"  Meta mapping updated: {count} fields for '{endpoint_name}'")


if __name__ == "__main__":
    asyncio.run(main())
