"""Regression: `alembic upgrade head` на пустой PostgreSQL должен строить
рабочую схему целиком, включая raw-слой и мета-маппинг.

Раньше тесты работали только на заранее подготовленной SQLite-фикстуре,
поэтому отсутствие raw-таблиц и падение миграции 011 на чистой базе
не замечались: первый же sync падал с `relation "raw_course" does not exist`.
"""

import asyncio
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

RAW_TABLES = {
    "raw_course",
    "raw_section",
    "raw_unit",
    "raw_lesson",
    "raw_step",
    "raw_course_grade",
    "raw_certificate",
    "raw_submission",
    "raw_attempt",
    "raw_course_benefit_by_month",
    "raw_course_benefit",
    "raw_course_review",
    "raw_course_review_summary",
    "raw_comment",
    "raw_user",
    "raw_sync_state",
}

APP_TABLES = {
    "users",
    "courses",
    "student_enrollments",
    "submissions",
    "financial_snapshots",
    "student_marts",
    "mart_modules",
    "mart_lessons",
    "mart_steps",
    "mart_comments",
    "mart_certificates",
    "mart_reviews",
    "meta_endpoint",
    "meta_field_mapping",
}


def _pg_url() -> str | None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    url = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not url or not url.startswith("postgresql"):
        return None
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), timeout=2):
            pass
    except OSError:
        return None
    return url


PG_URL = _pg_url()
pytestmark = pytest.mark.skipif(PG_URL is None, reason="Нет PostgreSQL (DATABASE_URL в .env)")


def _connect_kwargs(parsed, database: str) -> dict:
    return {
        "host": parsed.host or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": database,
    }


@pytest.mark.asyncio
async def test_alembic_upgrade_head_on_empty_database():
    parsed = make_url(PG_URL)
    db_name = f"stepik_fresh_{uuid.uuid4().hex[:10]}"

    admin = await asyncpg.connect(**_connect_kwargs(parsed, "postgres"))
    try:
        await admin.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin.close()

    temp_url = parsed.set(database=db_name).render_as_string(hide_password=False)
    env = {**os.environ, "DATABASE_URL": temp_url}

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        assert proc.returncode == 0, f"alembic upgrade head failed:\n{proc.stdout}\n{proc.stderr}"

        conn = await asyncpg.connect(**_connect_kwargs(parsed, db_name))
        try:
            tables = {
                row["table_name"]
                for row in await conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            }
            assert tables >= RAW_TABLES, f"raw tables missing: {sorted(RAW_TABLES - tables)}"
            assert tables >= APP_TABLES, f"app tables missing: {sorted(APP_TABLES - tables)}"

            expected_head = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini"))).get_heads()[0]
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == expected_head

            assert await conn.fetchval("SELECT count(*) FROM meta_endpoint") == 15
            assert await conn.fetchval("SELECT count(*) FROM meta_field_mapping") >= 70

            mappings = {
                (row["endpoint_name"], row["api_field"]): row["db_column"]
                for row in await conn.fetch("SELECT endpoint_name, api_field, db_column FROM meta_field_mapping")
            }
            assert mappings[("courses", "id")] == "course_id"
            assert mappings[("courses", "sections")] == "section_ids"
            assert mappings[("courses", "review_summary")] == "review_summary_json"
            assert mappings[("course_grades", "course")] == "course_id"
            assert mappings[("submissions", "id")] == "submission_id"
            assert mappings[("users", "id")] == "user_id"

            unique_indexes = {
                row["indexname"]
                for row in await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE tablename = 'raw_submission'"
                )
            }
            assert "uq_raw_submission_submission_id" in unique_indexes

            submission_columns = {
                row["column_name"]
                for row in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'raw_submission'"
                )
            }
            assert {"submission_id", "step", "attempt", "status", "time", "score"} <= submission_columns
        finally:
            await conn.close()
    finally:
        admin = await asyncpg.connect(**_connect_kwargs(parsed, "postgres"))
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        finally:
            await admin.close()
