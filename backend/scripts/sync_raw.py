"""Sync raw tables from the Stepik API (thin CLI over ``app.services.raw_sync``).

The application already runs the same pipeline from the panel; this script is
for development/diagnostics. It no longer reimplements pagination, cursors and
upserts — the package is the single source of truth.

Usage:
    python scripts/sync_raw.py                 # all groups, pipeline order
    python scripts/sync_raw.py submissions     # one group
    python scripts/sync_raw.py courses comments

Experimental raw endpoints outside the production pipeline are loaded with
``python scripts/explore_endpoint.py <name> --load``.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import async_session
from app.services import raw_sync
from app.services.crypto import decrypt_token

# Meta endpoint name → sync group. The package groups endpoints by subject:
# sections/units/lessons/steps are always refreshed together with courses.
ENDPOINT_GROUPS = {
    "courses": "structure",
    "sections": "structure",
    "units": "structure",
    "lessons": "structure",
    "steps": "structure",
    "course_grades": "grades",
    "certificates": "grades",
    "submissions": "submissions",
    "attempts": "submissions",
    "course_benefit_by_months": "financials",
    "course_benefits": "financials",
    "promo_codes": "financials",
    "course_review_summaries": "community",
    "course_reviews": "community",
    "comments": "community",
    "users": "users",
}

PIPELINE_ORDER = ("structure", "grades", "submissions", "financials", "community", "users")


async def _first_user_token() -> str | None:
    async with async_session() as session:
        row = (
            await session.execute(text("SELECT access_token FROM users ORDER BY created_at ASC, id ASC LIMIT 1"))
        ).fetchone()
    return decrypt_token(row[0]) if row else None


async def _course_ids() -> list[int]:
    async with async_session() as session:
        rows = await session.execute(text("SELECT course_id FROM raw_course"))
    ids = set()
    for (value,) in rows:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(ids)


async def _run_group(group: str, token: str | None) -> None:
    if group in ("structure", "grades", "submissions", "community", "users") and not token:
        print(f"  {group}: SKIP — no user token (log in to the panel first)")
        return

    async with async_session() as session:
        if group == "structure":
            await raw_sync.sync_courses_structure(session, token)
        elif group == "grades":
            course_ids = await _course_ids()
            if not course_ids:
                print("  grades: SKIP — raw_course is empty (run courses first)")
                return
            await raw_sync.sync_course_grades_and_certs(session, token, course_ids)
        elif group == "submissions":
            await raw_sync.sync_submissions(session, token)
        elif group == "financials":
            await raw_sync.sync_financials(session)
        elif group == "community":
            await raw_sync.sync_community(session, token)
        elif group == "users":
            await raw_sync.sync_users(session, token)
        else:  # pragma: no cover - guarded by the caller
            raise ValueError(f"unknown sync group: {group}")
        await session.commit()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sync raw tables from the Stepik API")
    parser.add_argument(
        "endpoints",
        nargs="*",
        help="Endpoint names to sync (default: all groups). Examples: courses, comments, submissions",
    )
    args = parser.parse_args()

    if args.endpoints:
        unknown = sorted(set(args.endpoints) - set(ENDPOINT_GROUPS))
        if unknown:
            parser.error(f"unknown endpoint(s): {', '.join(unknown)}")
        groups = []
        for name in args.endpoints:
            group = ENDPOINT_GROUPS[name]
            if group not in groups:
                groups.append(group)
    else:
        groups = list(PIPELINE_ORDER)

    token = await _first_user_token()
    if not token and "financials" not in groups:
        print("No user token found — log in to the panel first.")
        return 1

    for group in groups:
        print(f"[{group}]")
        await _run_group(group, token)
        print()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
