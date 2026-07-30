"""
Final comprehensive batch exploration of all remaining Stepik API endpoints.

For each endpoint in meta_endpoint (is_active=True, not yet documented):
  - Try multiple param strategies to get API data
  - Extract field names and types
  - Write fields_*.md document to docs/

Usage:
    python scripts/batch_explore_final.py
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.crypto import decrypt_token

settings = get_settings()
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
STEPIK_API = "https://stepik.org/api"

DONE = {
    "courses", "sections", "units", "lessons", "steps", "submissions",
    "comments", "attempts", "course_grades", "certificates",
    "course_benefit_by_months", "course_benefits", "course_review_summaries",
    "course_reviews", "progresses", "users", "achievements",
}

# Endpoints with their specific param strategies
# Each entry: (path, token_type, [(params_or_None, source_info)])
ENDPOINT_STRATEGIES = {}

def add_strategy(ep_name, path, token_type, param_sets):
    ENDPOINT_STRATEGIES[ep_name] = {"path": path, "token_type": token_type, "param_sets": param_sets}

# --- Define strategies for all remaining endpoints ---
add_strategy("achievement_progresses", "/achievement-progresses", "user", [{"ids[]": "__achievements__"}, None])
add_strategy("announcements", "/announcements", "user", [{"course": "__owned_course__"}, {"ids[]": "__owned_courses__"}, None])
add_strategy("assignments", "/assignments", "user", [None])
add_strategy("author_lists", "/author-lists", "user", [None])
add_strategy("course_benefit_summaries", "/course-benefit-summaries", "client", [{"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("course_lists", "/course-lists", "user", [None])
add_strategy("course_payments", "/course-payments", "user", [{"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("course_period_statistics", "/course-period-statistics", "user", [{"course": "__owned_course__"}, {"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("course_purchases", "/course-purchases", "user", [{"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("course_ranks", "/course-ranks", "user", [{"ids[]": "__courses__"}, None])
add_strategy("course_recommendations", "/course-recommendations", "user", [{"ids[]": "__courses__"}, None])
add_strategy("course_total_statistics", "/course-total-statistics", "user", [{"course": "__owned_course__"}, {"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("devices", "/devices", "user", [None])
add_strategy("discussion_proxies", "/discussion-proxies", "user", [None])
add_strategy("discussion_threads", "/discussion-threads", "user", [None])
add_strategy("email_addresses", "/email-addresses", "user", [None])
add_strategy("enrollments", "/enrollments", "user", [{"course": "__owned_course__"}, {"course": "__course__"}, None])
add_strategy("metrics", "/metrics", "user", [None])
add_strategy("profiles", "/profiles", "user", [{"ids[]": "__user__"}, None])
add_strategy("promo_codes", "/promo-codes", "user", [{"ids[]": "__owned_courses__"}, {"ids[]": "__courses__"}, None])
add_strategy("rubric_scores", "/rubric-scores", "user", [None])
add_strategy("rubrics", "/rubrics", "user", [None])
add_strategy("social_accounts", "/social-accounts", "user", [None])
add_strategy("social_profiles", "/social-profiles", "user", [{"ids[]": "__users__"}, None])
add_strategy("step_votes", "/step-votes", "user", [None])
add_strategy("subscriptions", "/subscriptions", "user", [None])
add_strategy("user_activity_summaries", "/user-activity-summaries", "user", [{"ids[]": "__user__"}, None])
add_strategy("user_code_runs", "/user-code-runs", "user", [None])
add_strategy("user_review_summaries", "/user-review-summaries", "user", [{"ids[]": "__users__"}, None])
add_strategy("views", "/views", "user", [None])
add_strategy("visited_courses", "/visited-courses", "user", [None])
add_strategy("votes", "/votes", "user", [None])
add_strategy("wish_lists", "/wish-lists", "user", [None])


async def get_user_token():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT access_token FROM users ORDER BY created_at DESC LIMIT 1"))
        row = r.fetchone()
    await engine.dispose()
    if row:
        return decrypt_token(row[0])
    return None


async def get_client_token():
    for cid_attr, csec_attr in [
        ("stepik_finance_client_id", "stepik_finance_client_secret"),
        ("stepik_client_id", "stepik_client_secret"),
    ]:
        cid = getattr(settings, cid_attr, "")
        csec = getattr(settings, csec_attr, "")
        if not cid:
            continue
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://stepik.org/oauth2/token/",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": csec, "scope": "read"},
                timeout=30.0,
            )
            if resp.status_code < 400:
                return resp.json().get("access_token")
    return None


async def fetch_data(path, token, params=None):
    url = f"{STEPIK_API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 429:
                retry = int(resp.headers.get("Retry-After", 5))
                await asyncio.sleep(retry)
                return await fetch_data(path, token, params)
            if resp.status_code >= 400:
                return None
            return resp.json()
    except Exception:
        return None


def extract_objects(data):
    for v in (data or {}).values():
        if isinstance(v, list):
            return v
    return []


def get_api_obj_name(data):
    for k, v in (data or {}).items():
        if isinstance(v, list):
            return k
    return None


def guess_type(val):
    if val is None:
        return "text"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "bigint" if abs(val) > 2_147_483_647 else "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "text"
    if isinstance(val, (list, dict)):
        return "jsonb"
    return "text"


async def resolve_sentinel(engine, sentinel):
    """Resolve a sentinel value to an actual param value."""
    if sentinel == "__user__":
        uid = settings.stepik_user_id
        return [str(uid)] if uid else None
    if sentinel == "__course__":
        async with engine.begin() as conn:
            r = await conn.execute(text("SELECT course_id FROM raw_course ORDER BY course_id LIMIT 1"))
            row = r.fetchone()
        return str(row[0]) if row else None
    if sentinel == "__courses__":
        async with engine.begin() as conn:
            r = await conn.execute(text("SELECT course_id FROM raw_course ORDER BY course_id LIMIT 5"))
            ids = [str(row[0]) for row in r if row[0] is not None]
        return ids if ids else None
    if sentinel == "__owned_course__":
        async with engine.begin() as conn:
            uid = str(settings.stepik_user_id) if settings.stepik_user_id else ""
            r = await conn.execute(
                text("SELECT course_id FROM raw_course WHERE owner_user_id = :uid ORDER BY course_id LIMIT 1"),
                {"uid": uid},
            )
            row = r.fetchone()
        return str(row[0]) if row else None
    if sentinel == "__owned_courses__":
        async with engine.begin() as conn:
            uid = str(settings.stepik_user_id) if settings.stepik_user_id else ""
            r = await conn.execute(
                text("SELECT course_id FROM raw_course WHERE owner_user_id = :uid ORDER BY course_id LIMIT 3"),
                {"uid": uid},
            )
            ids = [str(row[0]) for row in r if row[0] is not None]
        return ids if ids else None
    if sentinel == "__users__":
        async with engine.begin() as conn:
            r = await conn.execute(text("SELECT id FROM raw_user ORDER BY id LIMIT 5"))
            ids = [str(row[0]) for row in r if row[0] is not None]
        return ids if ids else None
    if sentinel == "__achievements__":
        async with engine.begin() as conn:
            r = await conn.execute(text('SELECT "id" FROM raw_achievement ORDER BY id LIMIT 3'))
            ids = [str(row[0]) for row in r if row[0] is not None]
        return ids if ids else None
    return None


async def resolve_params(engine, param_sets):
    """Resolve param sets with sentinels replaced by actual values."""
    resolved = []
    for param_set in param_sets:
        if param_set is None:
            resolved.append(None)
            continue
        new_params = {}
        skip = False
        for k, v in param_set.items():
            if isinstance(v, str) and v.startswith("__"):
                val = await resolve_sentinel(engine, v)
                if val is None:
                    skip = True  # Can't resolve this sentinel, skip this param set
                    break
                if isinstance(val, list):
                    if k == "ids[]" and val:
                        new_params["ids[]"] = val
                    elif k == "ids[]":
                        skip = True
                        break
                    else:
                        new_params[k] = val[0]
                else:
                    new_params[k] = val
            else:
                new_params[k] = v
        if not skip:
            resolved.append(new_params)
    return resolved


async def main():
    engine = create_async_engine(settings.database_url)

    # Get meta_endpoint info for all active endpoints
    async with engine.begin() as conn:
        r = await conn.execute(
            text("SELECT endpoint_name, raw_table, description FROM meta_endpoint WHERE is_active = true ORDER BY endpoint_name")
        )
        meta_info = {row[0]: {"raw_table": row[1], "description": row[2] or ""} for row in r.fetchall()}

    print(f"DONE endpoints: {len(DONE)}")
    print(f"Remaining: {len(ENDPOINT_STRATEGIES)}")

    user_token = await get_user_token()
    client_token = await get_client_token()

    if not user_token:
        print("ERROR: Could not get user token")
        return

    for ep_name, strat in ENDPOINT_STRATEGIES.items():
        path = strat["path"]
        token_type = strat["token_type"]
        param_sets = strat["param_sets"]
        token = client_token if token_type == "client" else user_token

        meta = meta_info.get(ep_name, {})
        raw_table = meta.get("raw_table", f"raw_{ep_name}")
        description = meta.get("description", "")

        doc_path = DOCS_DIR / f"fields_{ep_name}.md"

        print(f"\n--- {ep_name} (raw={raw_table}) ---")

        if not token:
            print("  No token available, writing NO DATA doc")
            doc_path.write_text(f"# {ep_name} — НЕТ ДАННЫХ (не удалось получить токен)\n")
            continue

        # Resolve params with sentinels
        resolved_params = await resolve_params(engine, param_sets)

        # Try each param set
        objects = None
        used_params = None
        data = None
        for p in resolved_params:
            print(f"  Trying: {p}")
            data = await fetch_data(path, token, p)
            if data is not None:
                objects = extract_objects(data)
                if objects:
                    used_params = p
                    print(f"  SUCCESS: {len(objects)} objects")
                    break
                print(f"  Empty response, keys: {list(data.keys())}")
            else:
                print(f"  No response")
            await asyncio.sleep(0.3)

        if not objects:
            # Last resort: bare endpoint
            print(f"  Trying bare endpoint...")
            data = await fetch_data(path, token, None)
            if data:
                objects = extract_objects(data)

        if not objects:
            print(f"  FAILED: no data")
            if doc_path.exists():
                print(f"  Keeping existing doc")
            else:
                doc_path.write_text(f"# {ep_name} — НЕТ ДАННЫХ (API не вернул данные)\n")
            await asyncio.sleep(0.5)
            continue

        # Extract fields
        sample = objects[0]
        api_obj_name = get_api_obj_name(data) or ep_name
        print(f"  Fields: {len(sample)}")

        fields = []
        for i, (key, val) in enumerate(sample.items(), 1):
            ftype = guess_type(val)
            fields.append({"index": i, "field": key, "type": ftype})
            print(f"    {i:3d}. {key:40s} ({ftype})")

        # Build doc
        singular = api_obj_name.rstrip("s") if api_obj_name else ep_name.rstrip("s")
        desc_text = (description.split(".")[0].strip() if description else ep_name.replace("_", " ").capitalize())

        lines = [f"# Поля {desc_text} ({raw_table})", ""]
        lines.append(f"Всего полей: {len(fields)}. Отметь Да/Нет в колонке Sync.")
        lines.append("")
        lines.append("| # | Поле API | Тип | Sync | Описание |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in fields:
            desc = ""
            if f["field"] == "id":
                desc = f"ID {desc_text} (→ {singular}_id)"
            lines.append(f"| {f['index']} | {f['field']} | {f['type']} | да | {desc} |")

        doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  -> {doc_path.name} written")

        await asyncio.sleep(0.5)

    await engine.dispose()
    print(f"\nDone! All docs in {DOCS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
