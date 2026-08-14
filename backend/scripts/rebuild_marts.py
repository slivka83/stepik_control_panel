"""
Rebuild all marts (витрины) from the raw layer without Stepik API calls.

Runs only the transform layer in the same order as sync_all:
    courses → enrollments → submissions → financials → community → students

Usage:
    python scripts/rebuild_marts.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.services import transform


async def _row_count(engine, table: str) -> int:
    async with engine.begin() as conn:
        r = await conn.execute(text(f"SELECT count(*) FROM {table}"))
        return int(r.scalar() or 0)


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    raw_courses = await _row_count(engine, "raw_course")
    if not raw_courses:
        print("ERROR: raw_course is empty — nothing to rebuild (run scripts/sync_raw.py first)")
        await engine.dispose()
        return 1

    steps = [
        ("courses", transform.transform_courses, {"user_id": None}, "courses"),
        ("enrollments", transform.transform_enrollments, {}, "student_enrollments"),
        ("submissions", transform.transform_submissions, {}, "submissions"),
        ("financials", transform.transform_financials, {}, "financial_snapshots"),
        ("community", transform.transform_community, {}, "financial_snapshots"),
        ("steps", transform.transform_steps, {}, "mart_steps"),
        ("comments", transform.transform_comments, {}, "mart_comments"),
        ("certificates", transform.transform_certificates, {}, "mart_certificates"),
        ("reviews", transform.transform_reviews, {}, "mart_reviews"),
        ("students", transform.transform_students, {}, "student_marts"),
    ]

    for name, fn, kwargs, table in steps:
        before = await _row_count(engine, table)
        print(f"=== {name} ===")
        async with session_factory() as session, session.begin():
            await fn(session, **kwargs)
        after = await _row_count(engine, table)
        print(f"  {table}: {before} → {after} rows")

    await engine.dispose()
    print("\nAll marts rebuilt from raw layer (no API calls)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
