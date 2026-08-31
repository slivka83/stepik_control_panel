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

from app.database import async_session, engine
from app.models import Base, Course, FinancialSnapshot, StudentEnrollment, Submission, User  # noqa: F401


@pytest.fixture(autouse=True)
def reset_stepik_http_client():
    """Общий httpx-клиент — модульный синглтон; сбрасываем его вокруг каждого
    теста, чтобы моки httpx.AsyncClient в тестах не зависели от порядка."""
    from app.services import stepik_api

    stepik_api._client = None
    yield
    stepik_api._client = None

RAW_TABLES = {
    # NOTE: column names AND types mirror the real PostgreSQL schema
    # (raw layer stores everything as TEXT). Keep them in sync with PG —
    # the schema-contract tests rely on this parity.
    "raw_course": """
        CREATE TABLE IF NOT EXISTS raw_course (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id TEXT,
            title TEXT,
            became_published_at TEXT,
            begin_date TEXT,
            updated_at TEXT,
            is_public TEXT,
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
            section_id TEXT,
            course TEXT,
            position TEXT,
            units TEXT,
            title TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_unit": """
        CREATE TABLE IF NOT EXISTS raw_unit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT,
            lesson_id TEXT,
            section_id TEXT,
            position TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_lesson": """
        CREATE TABLE IF NOT EXISTS raw_lesson (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT,
            steps TEXT,
            title TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_step": """
        CREATE TABLE IF NOT EXISTS raw_step (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id TEXT,
            lesson TEXT,
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
            user_id TEXT,
            score TEXT,
            last_viewed TEXT,
            date_joined TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_certificate": """
        CREATE TABLE IF NOT EXISTS raw_certificate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id TEXT,
            user_id TEXT,
            course_id TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_submission": """
        CREATE TABLE IF NOT EXISTS raw_submission (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id TEXT UNIQUE,
            step TEXT,
            "user" TEXT,
            status TEXT,
            "time" TEXT,
            score TEXT,
            attempt TEXT,
            eta TEXT,
            reply TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_attempt": """
        CREATE TABLE IF NOT EXISTS raw_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id TEXT UNIQUE,
            "user" TEXT,
            step TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_benefit_by_month": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit_by_month (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT,
            month TEXT,
            total_turnover TEXT,
            total_user_income TEXT,
            total_refunds TEXT,
            count_payments TEXT,
            count_refunds TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_benefit": """
        CREATE TABLE IF NOT EXISTS raw_course_benefit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benefit_id TEXT,
            course TEXT,
            amount TEXT,
            payment_amount TEXT,
            status TEXT,
            "time" TEXT,
            buyer TEXT,
            promo_code TEXT,
            currency_code TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_review": """
        CREATE TABLE IF NOT EXISTS raw_course_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT,
            course TEXT,
            "user" TEXT,
            score TEXT,
            create_date TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_course_review_summary": """
        CREATE TABLE IF NOT EXISTS raw_course_review_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_summary_id TEXT,
            average TEXT,
            count TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_comment": """
        CREATE TABLE IF NOT EXISTS raw_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE,
            "user" TEXT,
            target TEXT,
            "time" TEXT,
            thread TEXT,
            _raw_json TEXT,
            _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "raw_user": """
        CREATE TABLE IF NOT EXISTS raw_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            full_name TEXT,
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
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session):
    async def _override():
        yield db_session

    return _override


async def build_marts(session):
    """Пересобрать витрины структуры/комментариев/сертификатов/отзывов из raw-слоя.

    Хелпер для тестов API: после сидирования raw-данных витрины должны быть
    построены трансформами, т.к. API читает только mart_* таблицы.
    """
    from app.services import transform

    await transform.transform_steps(session)
    await transform.transform_comments(session)
    await transform.transform_certificates(session)
    await transform.transform_reviews(session)
