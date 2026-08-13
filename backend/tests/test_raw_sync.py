"""Tests for raw_sync service: API → raw table syncing."""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models import User
from app.services import raw_sync
from app.services.crypto import encrypt_token
from tests.test_schema_contract import needs_pg


def _make_user(session, stepik_id=12345):
    import uuid
    from datetime import timedelta

    user = User(
        id=uuid.uuid4(),
        stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(user)
    return user


async def _count_rows(session, table: str):
    r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return r.scalar()


def _fake_response(data: list, has_next=False):
    endpoint = "courses"
    if data:
        api_key = "courses"
    else:
        api_key = "courses"
    return {api_key: data, "meta": {"has_next": has_next}}


def _side_effect(pages: list[list[dict]]):
    """Create a side_effect for _request mock that returns pages of data."""
    results = []
    for page_data in pages:
        # Guess the endpoint key from the path
        results.append(
            {
                "courses": page_data,
                "course-grades": page_data,
                "certificates": page_data,
                "sections": page_data,
                "units": page_data,
                "lessons": page_data,
                "steps": page_data,
                "submissions": page_data,
                "attempts": page_data,
                "course-benefit-by-months": page_data,
                "course-benefits": page_data,
                "course-review-summaries": page_data,
                "comments": page_data,
                "meta": {"has_next": False},
            }
        )
    return results


# ─── sync_courses_structure ────────────────────────────────────────────


class TestSyncCoursesStructure:
    @pytest.mark.asyncio
    async def test_writes_to_raw_tables(self, db_session):
        from app.services.raw_sync import sync_courses_structure

        _make_user(db_session)
        await db_session.commit()

        fake_courses = [{"id": 101, "title": "Course 1", "sections": [1], "owner_user_id": 12345}]
        fake_sections = [{"id": 1, "course": 101, "units": [10], "section_id": 1}]
        fake_units = [{"id": 10, "lesson": 100, "section": 1, "unit_id": 10}]
        fake_lessons = [{"id": 100, "steps": [500], "lesson_id": 100}]
        fake_steps = [{"id": 500, "lesson": 100, "step_id": 500}]

        def request_side_effect(method, path, token, params=None):
            if "courses" in path and "teacher" in str(params):
                return {"courses": fake_courses, "meta": {"has_next": False}}
            if "sections" in path and "ids[]" in str(params):
                return {"sections": fake_sections, "meta": {"has_next": False}}
            if "units" in path and "ids[]" in str(params):
                return {"units": fake_units, "meta": {"has_next": False}}
            if "lessons" in path and "ids[]" in str(params):
                return {"lessons": fake_lessons, "meta": {"has_next": False}}
            if "steps" in path and "ids[]" in str(params):
                return {"steps": fake_steps, "meta": {"has_next": False}}
            return {}

        with (
            patch("app.services.raw_sync._request", side_effect=request_side_effect),
            patch("app.config.get_settings") as mock_settings,
        ):
            mock_settings.return_value.stepik_user_id = 12345
            await sync_courses_structure(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_course") == 1
        assert await _count_rows(db_session, "raw_section") == 1
        assert await _count_rows(db_session, "raw_unit") == 1
        assert await _count_rows(db_session, "raw_lesson") == 1
        assert await _count_rows(db_session, "raw_step") == 1

    @pytest.mark.asyncio
    async def test_writes_became_published_at_column(self, db_session):
        """Regression: колонка raw_course.became_published_at не заполнялась.

        meta_field_mapping не содержал поля became_published_at, поэтому
        loader (пишет только маппленные колонки) молча пропускал её —
        courses.published_at пустел, колонка «Опубликован» показывала «—».
        """
        from app.services.raw_sync import sync_courses_structure

        _make_user(db_session)
        await db_session.execute(
            text("""
                INSERT INTO meta_field_mapping
                    (endpoint_name, api_field, db_column, db_type, is_loaded)
                VALUES ('courses', 'became_published_at', 'became_published_at',
                        'datetime(timezone)', TRUE)
            """)
        )
        await db_session.commit()

        fake_courses = [
            {
                "id": 101,
                "title": "Course 1",
                "sections": [1],
                "owner_user_id": 12345,
                "is_public": True,
                "became_published_at": "2026-01-15T10:00:00Z",
            }
        ]
        fake_sections = [{"id": 1, "course": 101, "units": [10], "section_id": 1}]
        fake_units = [{"id": 10, "lesson": 100, "section": 1, "unit_id": 10}]
        fake_lessons = [{"id": 100, "steps": [500], "lesson_id": 100}]
        fake_steps = [{"id": 500, "lesson": 100, "step_id": 500}]

        def request_side_effect(method, path, token, params=None):
            if "courses" in path and "teacher" in str(params):
                return {"courses": fake_courses, "meta": {"has_next": False}}
            if "sections" in path and "ids[]" in str(params):
                return {"sections": fake_sections, "meta": {"has_next": False}}
            if "units" in path and "ids[]" in str(params):
                return {"units": fake_units, "meta": {"has_next": False}}
            if "lessons" in path and "ids[]" in str(params):
                return {"lessons": fake_lessons, "meta": {"has_next": False}}
            if "steps" in path and "ids[]" in str(params):
                return {"steps": fake_steps, "meta": {"has_next": False}}
            return {}

        with (
            patch("app.services.raw_sync._request", side_effect=request_side_effect),
            patch("app.config.get_settings") as mock_settings,
        ):
            mock_settings.return_value.stepik_user_id = 12345
            await sync_courses_structure(db_session, "fake_token")

        r = await db_session.execute(text("SELECT became_published_at, _raw_json FROM raw_course"))
        row = r.fetchone()
        assert row is not None, "raw_course пуст"
        assert row[0] == "2026-01-15T10:00:00Z", "became_published_at не записан в raw_course"
        assert '"id": 101' in row[1], "_raw_json не сохранён"


# ─── sync_course_grades_and_certs ──────────────────────────────────────


class TestSyncCourseGradesAndCerts:
    @pytest.mark.asyncio
    async def test_writes_grades_and_certs(self, db_session):
        from app.services.raw_sync import sync_course_grades_and_certs

        _make_user(db_session)
        await db_session.commit()

        fake_grades = [
            {"user": 1001, "course": 101, "score": 85, "last_viewed": 1700000000},
        ]
        fake_certs = [{"user_id": 1001, "course": 101}]

        def request_side_effect(method, path, token, params=None):
            if "course-grades" in path:
                return {"course-grades": fake_grades, "meta": {"has_next": False}}
            if "certificates" in path:
                return {"certificates": fake_certs, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_course_grades_and_certs(db_session, "fake_token", [101])

        assert await _count_rows(db_session, "raw_course_grade") == 1
        assert await _count_rows(db_session, "raw_certificate") == 1


# ─── sync_submissions ──────────────────────────────────────────────────


class TestSyncSubmissions:
    @pytest.mark.asyncio
    async def test_writes_submissions_and_attempts(self, db_session):
        from app.services.raw_sync import sync_submissions

        _make_user(db_session)
        await db_session.commit()

        # Need steps to exist in raw_step for submission sync
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (500, 10, '{}')
        """)
        )
        await db_session.commit()

        # Regression: API НЕ возвращает step в объекте submission — шаг
        # известен только из контекста ?step= и должен инжектиться в raw
        fake_subs = [
            {
                "id": 1000,
                "status": "correct",
                "time": "2026-07-15T10:00:00Z",
                "score": 1.0,
                "reply": {},
                "attempt": 10,
            },
        ]
        fake_attempts = [{"id": 10, "user": 12345, "step": 500}]

        def request_side_effect(method, path, token, params=None):
            if "submissions" in path and "step" in str(params):
                return {"submissions": fake_subs, "meta": {"has_next": False}}
            if "submissions" in path and "course" in str(params):
                return {"submissions": [], "meta": {"has_next": False}}
            if "attempts" in path:
                return {"attempts": fake_attempts, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_submissions(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_submission") == 1
        assert await _count_rows(db_session, "raw_attempt") == 1
        r = await db_session.execute(text("SELECT step, _raw_json FROM raw_submission"))
        step_col, raw = r.fetchone()
        assert step_col == "500"
        assert json.loads(raw).get("step") == 500

    @pytest.mark.asyncio
    async def test_upsert_with_conflict_clause_deduplicates(self, db_session):
        """Regression: sync падал на PG с «no unique or exclusion constraint
        matching the ON CONFLICT specification».

        _upsert_raw_table генерирует ON CONFLICT (submission_id), но таблица
        не имела unique-констрейнта. Воспроизводим upsert-путь с пересечением
        страниц: одна и та же submission на двух страницах должна задедупиться.
        """
        from app.services.raw_sync import sync_submissions

        _make_user(db_session)
        await db_session.execute(
            text("""
            INSERT INTO meta_field_mapping
                (endpoint_name, api_field, db_column, db_type, is_loaded)
            VALUES ('submissions', 'id', 'submission_id', 'bigint', TRUE)
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json)
            VALUES (500, 10, '{}')
        """)
        )
        await db_session.commit()

        page1 = [
            {
                "id": 1000,
                "step": 500,
                "status": "correct",
                "time": "2026-07-15T10:00:00Z",
                "score": 1.0,
                "reply": {},
                "attempt": 10,
            },
        ]
        page2 = [
            {
                "id": 1000,
                "step": 500,
                "status": "correct",
                "time": "2026-07-15T10:00:00Z",
                "score": 1.0,
                "reply": {},
                "attempt": 10,
            },
            {
                "id": 1001,
                "step": 500,
                "status": "wrong",
                "time": "2026-07-15T11:00:00Z",
                "score": 0.0,
                "reply": {},
                "attempt": 11,
            },
        ]

        def request_side_effect(method, path, token, params=None):
            if "submissions" in path and "step" in str(params) and str(params).startswith("{'step'"):
                page = params.get("page", 1)
                if page == 1:
                    return {"submissions": page1, "meta": {"has_next": True}}
                return {"submissions": page2, "meta": {"has_next": False}}
            if "submissions" in path and "course" in str(params):
                return {"submissions": [], "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_submissions(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_submission") == 2, (
            "ON CONFLICT не сработал: дубликат submission_id 1000 не задедуплен"
        )


# ─── sync_financials ───────────────────────────────────────────────────


class TestSyncFinancials:
    @pytest.mark.asyncio
    async def test_writes_financial_tables(self, db_session):
        from app.services.raw_sync import sync_financials

        _make_user(db_session)
        await db_session.commit()

        fake_by_months = [
            {
                "year": 2026,
                "month": 7,
                "total_turnover": 10000,
                "total_user_income": 8000,
                "total_refunds": 200,
                "count_payments": 10,
                "count_refunds": 1,
            },
        ]
        fake_benefits = [
            {
                "id": 1,
                "course": 101,
                "amount": 1000,
                "payment_amount": 1200,
                "status": "completed",
                "time": "2026-07-01T10:00:00Z",
                "buyer": 1001,
                "promo_code": None,
                "currency_code": "RUB",
            },
        ]

        def request_side_effect(method, path, token, params=None):
            if "course-benefit-by-months" in path:
                return {"course-benefit-by-months": fake_by_months, "meta": {"has_next": False}}
            if "course-benefits" in path:
                return {"course-benefits": fake_benefits, "meta": {"has_next": False}}
            return {}

        with (
            patch("app.services.raw_sync.get_finance_token", return_value="finance_token"),
            patch("app.services.raw_sync._request", side_effect=request_side_effect),
        ):
            await sync_financials(db_session)

        assert await _count_rows(db_session, "raw_course_benefit_by_month") == 1
        assert await _count_rows(db_session, "raw_course_benefit") == 1

    @pytest.mark.asyncio
    async def test_skips_without_token(self, db_session):
        from app.services.raw_sync import sync_financials

        with patch("app.services.raw_sync.get_finance_token", return_value=None):
            await sync_financials(db_session)


# ─── sync_community ────────────────────────────────────────────────────


class TestSyncCommunity:
    @pytest.mark.asyncio
    async def test_writes_reviews_and_comments(self, db_session):
        from app.services.raw_sync import sync_community

        _make_user(db_session)
        await db_session.commit()

        await db_session.execute(
            text("""
            INSERT INTO raw_course (course_id, review_summary_json, _raw_json)
            VALUES (101, '[42]', '{"id": 101, "review_summary": 42}')
        """)
        )
        await db_session.commit()

        fake_reviews = [{"id": 42, "average": 4.5, "count": 100}]
        fake_comments = [{"id": 1, "user": 1001, "target": 101, "time": "2026-07-15T10:00:00Z", "thread": ""}]

        def request_side_effect(method, path, token, params=None):
            if "course-review-summaries" in path:
                return {"course-review-summaries": fake_reviews, "meta": {"has_next": False}}
            if "comments" in path:
                return {"comments": fake_comments, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_community(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_course_review_summary") == 1
        assert await _count_rows(db_session, "raw_comment") == 1

    @pytest.mark.asyncio
    async def test_skips_failing_comments_course_without_aborting(self, db_session):
        """Regression: сбой /comments по одному курсу убивал весь sync_community.

        На live PG упавший этап оставлял снапшот без community-блока
        (после transform_financials) — плашки Отзывы/Комментарии обнулялись.
        """
        from app.services.raw_sync import sync_community
        from app.services.stepik_api import StepikAPIError

        _make_user(db_session)
        await db_session.execute(
            text("""
            INSERT INTO meta_field_mapping
                (endpoint_name, api_field, db_column, db_type, is_loaded)
            VALUES ('comments', 'id', 'comment_id', 'bigint', TRUE)
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_course (course_id, review_summary_json, _raw_json) VALUES
                (101, '[42]', '{"id": 101, "review_summary": 42}'),
                (102, '[43]', '{"id": 102, "review_summary": 43}')
        """)
        )
        await db_session.commit()

        fake_reviews = [
            {"id": 42, "average": 4.5, "count": 100},
            {"id": 43, "average": 5.0, "count": 50},
        ]
        fake_comments = [{"id": 1, "user": 1001, "target": 101, "time": "2026-07-15T10:00:00Z", "thread": ""}]

        def request_side_effect(method, path, token, params=None):
            if "course-review-summaries" in path:
                return {"course-review-summaries": fake_reviews, "meta": {"has_next": False}}
            if "comments" in path:
                if params.get("course") == 101:
                    raise StepikAPIError(500, "Internal Server Error")
                return {"comments": fake_comments, "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_community(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_course_review_summary") == 2
        assert await _count_rows(db_session, "raw_comment") == 1, (
            "comments живого курса не записаны — sync прервался на упавшем курсе"
        )


class TestSyncSubmissionsStep404:
    @pytest.mark.asyncio
    async def test_skips_404_steps_without_aborting(self, db_session):
        """Regression: sync падал на live PG с StepikAPIError 404.

        Stepik возвращает 404 для удалённых/недоступных шагов —
        один такой шаг не должен убивать весь sync_submissions.
        """
        from app.services.raw_sync import sync_submissions
        from app.services.stepik_api import StepikAPIError

        _make_user(db_session)
        await db_session.execute(
            text("""
            INSERT INTO meta_field_mapping
                (endpoint_name, api_field, db_column, db_type, is_loaded)
            VALUES ('submissions', 'id', 'submission_id', 'bigint', TRUE)
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES
                (500, 10, '{}'),
                (501, 11, '{}')
        """)
        )
        await db_session.commit()

        dead_step = {"id": 500, "status": "correct", "time": "2026-07-15T10:00:00Z"}
        live_step = {"id": 2000, "status": "wrong", "time": "2026-07-15T11:00:00Z"}

        def request_side_effect(method, path, token, params=None):
            if "submissions" in path and "step" in str(params):
                if params.get("step") == 500:
                    raise StepikAPIError(404, "Not found")
                return {"submissions": [live_step], "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_submissions(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_submission") == 1, (
            "submission живого шага не записана — sync прервался на 404-шаге"
        )
        r = await db_session.execute(text("SELECT submission_id FROM raw_submission"))
        assert r.scalar() == "2000"


class TestSyncSubmissionsTheoryStep400:
    @pytest.mark.asyncio
    async def test_skips_400_theory_steps_without_aborting(self, db_session):
        """Regression: sync падал на live PG с StepikAPIError 400.

        Stepik возвращает 400 «Bad step parameter» для теоретических (text)
        шагов, у которых нет решений, — один такой шаг не должен убивать
        весь sync_submissions (как и 404 для удалённых).
        """
        from app.services.raw_sync import sync_submissions
        from app.services.stepik_api import StepikAPIError

        _make_user(db_session)
        await db_session.execute(
            text("""
            INSERT INTO meta_field_mapping
                (endpoint_name, api_field, db_column, db_type, is_loaded)
            VALUES ('submissions', 'id', 'submission_id', 'bigint', TRUE)
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES
                (500, 10, '{"block": {"name": "text"}}'),
                (501, 11, '{}')
        """)
        )
        await db_session.commit()

        theory_step = {"id": 500, "status": "correct", "time": "2026-07-15T10:00:00Z"}
        live_step = {"id": 2000, "status": "wrong", "time": "2026-07-15T11:00:00Z"}

        def request_side_effect(method, path, token, params=None):
            if "submissions" in path and "step" in str(params):
                if params.get("step") == 500:
                    raise StepikAPIError(400, '{"detail": "Bad step parameter."}')
                return {"submissions": [live_step], "meta": {"has_next": False}}
            return {}

        with patch("app.services.raw_sync._request", side_effect=request_side_effect):
            await sync_submissions(db_session, "fake_token")

        assert await _count_rows(db_session, "raw_submission") == 1, (
            "submission живого шага не записана — sync прервался на 400-шаге"
        )
        r = await db_session.execute(text("SELECT submission_id FROM raw_submission"))
        assert r.scalar() == "2000"


class TestSyncCommunityStrBind:
    @pytest.mark.asyncio
    async def test_course_id_bound_as_str(self, db_session):
        """Regression: live PG падал с asyncpg DataError «expected str, got int».

        raw_course.course_id — TEXT в PG, а sync_community передавал int из API
        в WHERE course_id = :cid. SQLite это не ловит (динамическая типизация).
        """
        from app.services.raw_sync import sync_community

        _make_user(db_session)
        await db_session.execute(
            text("""
            INSERT INTO raw_course (course_id, review_summary_json, _raw_json)
            VALUES (291904, '5', '{"id": 291904}')
        """)
        )
        await db_session.commit()

        binds = []
        real_execute = db_session.execute

        async def spy(stmt, params=None):
            if "review_summary_json" in str(stmt) and params:
                binds.append(params)
            return await real_execute(stmt, params)

        db_session.execute = spy

        def request_side_effect(method, path, token, params=None):
            if "review-summaries" in path:
                return {"course-review-summaries": [{"id": 5, "course": 291904}], "meta": {"has_next": False}}
            return {}

        with (
            patch("app.services.raw_sync._request", side_effect=request_side_effect),
            patch("app.services.raw_sync._paginated_fetch", return_value=[]),
        ):
            await sync_community(db_session, "fake_token")

        assert binds, "запрос к review_summary_json не выполнялся"
        assert all(isinstance(b.get("cid"), str) for b in binds if "cid" in b), (
            "course_id должен биндиться как str (TEXT-колонка в live PG)"
        )


@needs_pg
async def test_upsert_syncs_stale_sequence_on_pg():
    """Regression: live PG падал с UniqueViolationError (raw_comment_pkey).

    raw_comment лежит с явными id, а serial-последовательность осталась
    «из прошлой жизни» — upsert-путь (INSERT без id) попадал nextval в
    занятый диапазон и убивал sync. Транзакция с rollback — данные целы.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.services.raw_sync import _upsert_raw_table
    from tests.test_schema_contract import PG_URL

    engine = create_async_engine(PG_URL)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            trans = await session.begin()
            try:
                await session.execute(text("TRUNCATE TABLE raw_comment RESTART IDENTITY"))
                await session.execute(
                    text(
                        "INSERT INTO raw_comment (id, comment_id, _raw_json) VALUES (100, '1', '{}'), (101, '2', '{}')"
                    )
                )
                await session.execute(text("SELECT setval('raw_comment_id_seq', 1, false)"))
                await _upsert_raw_table(
                    session,
                    "raw_comment",
                    [{"id": 9999, "comment_id": "3"}],
                    {"comment_id": "comment_id"},
                )
                r = await session.execute(text("SELECT count(*) FROM raw_comment WHERE comment_id = '3'"))
                assert r.scalar() == 1, "upsert не записал новый comment (pkey collision до фикса)"
                r = await session.execute(text("SELECT last_value FROM raw_comment_id_seq"))
                assert r.scalar() >= 101, "последовательность не подтянута после upsert"
            finally:
                # begin()-контекст коммитит на выходе — только явный rollback
                await trans.rollback()
    finally:
        await engine.dispose()


# ─── sync_users ─────────────────────────────────────────────────────────


class TestSyncUsers:
    """Regression: raw_user (имена студентов) не входил в пайплайн кнопки —
    витрина студентов показывала fallback «Студент {id}»."""

    async def _seed_user_mapping(self, db_session):
        for api_field, db_col in [
            ("id", "user_id"),
            ("first_name", "first_name"),
            ("last_name", "last_name"),
            ("full_name", "full_name"),
        ]:
            await db_session.execute(
                text("""
                    INSERT INTO meta_field_mapping
                        (endpoint_name, api_field, db_column, db_type, is_loaded)
                    VALUES ('users', :f, :c, 'text', TRUE)
                """),
                {"f": api_field, "c": db_col},
            )

    async def test_syncs_names_into_raw_user(self, db_session):
        import uuid as _uuid

        from app.models import Course, StudentEnrollment, Submission

        user = _make_user(db_session)
        course = Course(id=_uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        db_session.add(course)
        await db_session.flush()
        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(StudentEnrollment(id=_uuid.uuid4(), course_id=course.id, student_id=7, last_viewed_at=now))
        db_session.add(
            Submission(
                id=_uuid.uuid4(),
                stepik_submission_id=2001,
                stepik_step_id=10,
                course_id=course.id,
                status="correct",
                score=1.0,
                submission_time=now,
                user_id=8,
                is_author=False,
            )
        )
        await db_session.execute(
            text("INSERT INTO raw_course_grade (user_id, course_id, _raw_json) VALUES (9, 100, '{}')")
        )
        await self._seed_user_mapping(db_session)
        await db_session.commit()

        def fake_fetch(path, token, key, extra=None):
            ids = extra.get("ids[]", [])
            return [{"id": int(i), "first_name": f"Name{i}", "last_name": f"Last{i}"} for i in ids]

        with patch("app.services.raw_sync._paginated_fetch", side_effect=fake_fetch):
            await raw_sync.sync_users(db_session, "token")

        r = await db_session.execute(text("SELECT user_id, first_name, last_name FROM raw_user"))
        names = {(str(row[0]), str(row[1]), str(row[2])) for row in r}
        assert ("7", "Name7", "Last7") in names
        assert ("8", "Name8", "Last8") in names
        assert ("9", "Name9", "Last9") in names
        assert len(names) == 3

    async def test_batches_ids_by_100(self, db_session):
        import uuid as _uuid

        from app.models import Course, StudentEnrollment

        user = _make_user(db_session)
        course = Course(id=_uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        db_session.add(course)
        await db_session.flush()
        now = datetime.now(UTC).replace(tzinfo=None)
        for sid in range(1, 251):
            db_session.add(StudentEnrollment(id=_uuid.uuid4(), course_id=course.id, student_id=sid, last_viewed_at=now))
        await db_session.commit()

        batches = []

        async def fake_fetch(path, token, key, extra=None):
            ids = extra.get("ids[]", [])
            batches.append(len(ids))
            return []

        with patch("app.services.raw_sync._paginated_fetch", side_effect=fake_fetch):
            await raw_sync.sync_users(db_session, "token")

        assert batches == [100, 100, 50]

    async def test_filters_non_numeric_ids(self, db_session):
        import uuid as _uuid

        from app.models import Course, StudentEnrollment

        user = _make_user(db_session)
        course = Course(id=_uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
        db_session.add(course)
        await db_session.flush()
        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(StudentEnrollment(id=_uuid.uuid4(), course_id=course.id, student_id=7, last_viewed_at=now))
        # Garbage from raw_comment.user (OAuth client name) must not break the sync
        await db_session.execute(
            text("INSERT INTO raw_comment (comment_id, \"user\", _raw_json) VALUES (1, 'stepik_panel', '{}')")
        )
        await db_session.commit()

        fetched_ids = []

        async def fake_fetch(path, token, key, extra=None):
            fetched_ids.extend(extra.get("ids[]", []))
            return []

        with patch("app.services.raw_sync._paginated_fetch", side_effect=fake_fetch):
            await raw_sync.sync_users(db_session, "token")

        assert fetched_ids == ["7"]
