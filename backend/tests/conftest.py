import os

from cryptography.fernet import Fernet

os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["STEPIK_CLIENT_ID"] = "test_client_id"
os.environ["STEPIK_CLIENT_SECRET"] = "test_client_secret"

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models import Base, User, Course, StudentEnrollment, Submission, FinancialSnapshot  # noqa: F401
from app.database import engine, get_db, async_session

RAW_TABLES = {
    "raw_course": """
        CREATE TABLE IF NOT EXISTS raw_course (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            title TEXT,
            became_published_at TEXT,
            begin_date TEXT,
            updated_at TEXT,
            is_public INTEGER,
            is_published TEXT,
            review_summary INTEGER,
            review_summary_json TEXT,
            section_ids TEXT,
            owner_user_id INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_section": """
        CREATE TABLE IF NOT EXISTS raw_section (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER,
            course INTEGER,
            units TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_unit": """
        CREATE TABLE IF NOT EXISTS raw_unit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER,
            lesson_id INTEGER,
            section_id INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_lesson": """
        CREATE TABLE IF NOT EXISTS raw_lesson (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            steps TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_step": """
        CREATE TABLE IF NOT EXISTS raw_step (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id INTEGER,
            lesson INTEGER,
            progress TEXT,
            block TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_grade": """
        CREATE TABLE IF NOT EXISTS raw_course_grade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id TEXT,
            user_id INTEGER,
            score INTEGER,
            last_viewed TEXT,
            date_joined TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_certificate": """
        CREATE TABLE IF NOT EXISTS raw_certificate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id INTEGER,
            user_id INTEGER,
            course INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_submission": """
        CREATE TABLE IF NOT EXISTS raw_submission (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER,
            step INTEGER,
            "user" INTEGER,
            status TEXT,
            "time" TEXT,
            score TEXT,
            attempt INTEGER,
            eta TEXT,
            reply TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_attempt": """
        CREATE TABLE IF NOT EXISTS raw_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER,
            user_id INTEGER,
            step INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_benefit_by_month": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit_by_month (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            month INTEGER,
            total_turnover TEXT,
            total_user_income TEXT,
            total_refunds TEXT,
            count_payments INTEGER,
            count_refunds INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_benefit": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benefit_id INTEGER,
            course INTEGER,
            amount TEXT,
            payment_amount TEXT,
            status TEXT,
            "time" TEXT,
            buyer INTEGER,
            promo_code TEXT,
            currency_code TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_review_summary": """
        CREATE TABLE IF NOT EXISTS raw_course_review_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_summary_id INTEGER,
            average TEXT,
            count INTEGER,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_comment": """
        CREATE TABLE IF NOT EXISTS raw_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER,
            "user" INTEGER,
            target INTEGER,
            "time" TEXT,
            thread TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_sync_state": """
        CREATE TABLE IF NOT EXISTS raw_sync_state (
            endpoint_name TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (endpoint_name, key)
        )
    """,
}


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        for name, ddl in RAW_TABLES.items():
            await conn.execute(text(ddl))

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        for name in RAW_TABLES:
            await conn.execute(text(f"DROP TABLE IF EXISTS {name}"))


@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session):
    async def _override():
        yield db_session
    return _override
