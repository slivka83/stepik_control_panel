"""Тесты эндпоинта GET /api/courses/{course_id}/funnel.

Воронка прохождения курса: «Записались» → «Модуль N» (distinct-студенты с
решением в модуле или позже) → «Получили сертификат».
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, StudentEnrollment, Submission, User
from app.services.crypto import encrypt_token
from tests.conftest import build_marts

client = TestClient(app, raise_server_exceptions=False)


def _make_user(stepik_id: int = 64381531) -> User:
    return User(
        id=uuid.uuid4(),
        stepik_id=stepik_id,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )


def _make_course(user_id, stepik_course_id, title="Python 101") -> Course:
    return Course(
        id=uuid.uuid4(),
        user_id=user_id,
        stepik_course_id=stepik_course_id,
        title=title,
        status="published",
    )


def _make_submission(course_id, submission_id, step_id, status, user_id=None) -> Submission:
    return Submission(
        id=uuid.uuid4(),
        stepik_submission_id=submission_id,
        stepik_step_id=step_id,
        course_id=course_id,
        status=status,
        user_id=user_id,
        submission_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_author=False,
    )


def _make_enrollment(course_id, student_id, certificate_issued=False) -> StudentEnrollment:
    return StudentEnrollment(
        id=uuid.uuid4(),
        course_id=course_id,
        student_id=student_id,
        certificate_issued=certificate_issued,
    )


def _override_api(db_session, user):
    async def override_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


async def _call(db_session, user, course_id, view=None):
    await build_marts(db_session)
    _override_api(db_session, user)
    try:
        url = f"/api/courses/{course_id}/funnel"
        if view:
            url += f"?view={view}"
        return client.get(url)
    finally:
        app.dependency_overrides.clear()


async def _seed_structure(db_session, stepik_course_id=208966):
    """raw-слой: 2 модуля, модуль 1 — урок с шагами 500/501, модуль 2 — 502/503."""
    await db_session.execute(text("DELETE FROM raw_section"))
    await db_session.execute(text("DELETE FROM raw_unit"))
    await db_session.execute(text("DELETE FROM raw_lesson"))
    await db_session.execute(text("DELETE FROM raw_step"))
    await db_session.execute(
        text(
            "INSERT INTO raw_section (section_id, course, position, title) VALUES "
            "('1', :cid, '1', 'Module A'), ('2', :cid, '2', 'Module B')"
        ),
        {"cid": str(stepik_course_id)},
    )
    await db_session.execute(
        text(
            "INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES "
            "('u1', '10', '1', '1'), ('u2', '11', '2', '1')"
        )
    )
    await db_session.execute(
        text("INSERT INTO raw_lesson (lesson_id, title, steps) VALUES ('10', 'L1', :s1), ('11', 'L2', :s2)"),
        {"s1": json.dumps([500, 501]), "s2": json.dumps([502, 503])},
    )


class TestCourseFunnelOwnership:
    async def test_404_unknown_course(self, db_session):
        user = _make_user()
        db_session.add(user)
        await db_session.commit()
        resp = await _call(db_session, user, str(uuid.uuid4()))
        assert resp.status_code == 404

    async def test_404_foreign_course(self, db_session):
        owner = _make_user(1)
        other = _make_user(2)
        course = _make_course(owner.id, 100)
        db_session.add_all([owner, other, course])
        await db_session.commit()
        resp = await _call(db_session, other, str(course.id))
        assert resp.status_code == 404

    async def test_404_invalid_uuid(self, db_session):
        user = _make_user()
        db_session.add(user)
        await db_session.commit()
        resp = await _call(db_session, user, "not-a-uuid")
        assert resp.status_code == 404


class TestCourseFunnelStages:
    async def test_empty_structure_returns_enrolled_and_certificate(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 999)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        resp = await _call(db_session, user, str(course.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["course"]["title"] == course.title
        assert [s["key"] for s in data["stages"]] == ["enrolled", "certificate"]
        assert data["stages"][0]["value"] == 1
        assert data["stages"][1]["value"] == 0

    async def test_module_stages_cumulative_distinct(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all(
            [
                user,
                course,
                _make_enrollment(course.id, 1),
                _make_enrollment(course.id, 2),
                _make_enrollment(course.id, 3),
            ]
        )
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                # user 1: дошёл только до модуля 1
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                # user 2: модуль 1 и модуль 2
                _make_submission(course.id, 2, 501, "correct", user_id=2),
                _make_submission(course.id, 3, 502, "correct", user_id=2),
                # user 3: только модуль 2 (пропустил первый)
                _make_submission(course.id, 4, 503, "wrong", user_id=3),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "module", "module", "certificate"]
        assert [s["module_number"] for s in stages if s["key"] == "module"] == [1, 2]
        assert [s["label"] for s in stages] == ["Записались", "Модуль 1. Module A", "Модуль 2. Module B", "Получили сертификат"]

        values = [s["value"] for s in stages]
        assert values == [3, 3, 2, 0]

    async def test_funnel_is_monotonic_decreasing(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1), _make_enrollment(course.id, 2)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                _make_submission(course.id, 2, 502, "correct", user_id=2),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        values = [s["value"] for s in resp.json()["stages"]]
        assert values == sorted(values, reverse=True)

    async def test_certificate_stage_count(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all(
            [
                user,
                course,
                _make_enrollment(course.id, 1, certificate_issued=True),
                _make_enrollment(course.id, 2, certificate_issued=True),
                _make_enrollment(course.id, 3),
            ]
        )
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                _make_submission(course.id, 2, 501, "correct", user_id=2),
                _make_submission(course.id, 3, 503, "correct", user_id=3),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        assert stages[0]["value"] == 3
        assert [s["value"] for s in stages if s["key"] == "module"] == [3, 1]
        assert stages[-1]["key"] == "certificate"
        assert stages[-1]["value"] == 2

    async def test_author_submissions_excluded(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=99,
                    stepik_step_id=500,
                    course_id=course.id,
                    status="correct",
                    submission_time=datetime(2026, 1, 1, tzinfo=UTC),
                    is_author=True,
                ),
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=98,
                    stepik_step_id=502,
                    course_id=course.id,
                    status="correct",
                    user_id=5,
                    submission_time=datetime(2026, 1, 1, tzinfo=UTC),
                    is_author=False,
                ),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        # авторское решение (шаг 500, is_author=True) не добавило пользователя
        # в модуль 1; user 5 (шаг 502) виден в модуле 2 и «в модуле 1 или позже»
        assert [s["value"] for s in stages] == [1, 1, 1, 0]

    async def test_unattributable_steps_are_skipped(self, db_session):
        """Regression: шаги submissions вне структуры не ломают воронку."""
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                _make_submission(course.id, 1, 999, "correct", user_id=1),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        assert [s["value"] for s in stages] == [1, 0, 0, 0]

    async def test_no_data_returns_zeros(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "module", "module", "certificate"]
        assert all(s["value"] == 0 for s in stages)

    async def test_section_without_steps_counts_as_module(self, db_session):
        """Модуль без атрибутированных шагов остаётся в воронке (значение = следующий этап)."""
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await db_session.execute(
            text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('3', :cid, '3', 'Empty')"),
            {"cid": "208966"},
        )
        db_session.add_all([_make_submission(course.id, 1, 500, "correct", user_id=1)])
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "module", "module", "module", "certificate"]
        assert [s["label"] for s in stages if s["key"] == "module"] == [
            "Модуль 1. Module A",
            "Модуль 2. Module B",
            "Модуль 3. Empty",
        ]
        assert [s["value"] for s in stages if s["key"] == "module"] == [1, 0, 0]


class TestCourseFunnelLessonsView:
    """view=lessons: воронка по урокам (distinct-студенты с решением в уроке или позже)."""

    async def test_lessons_view_cumulative_distinct(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all(
            [
                user,
                course,
                _make_enrollment(course.id, 1),
                _make_enrollment(course.id, 2),
                _make_enrollment(course.id, 3),
            ]
        )
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                _make_submission(course.id, 2, 501, "correct", user_id=2),
                _make_submission(course.id, 3, 502, "correct", user_id=2),
                _make_submission(course.id, 4, 503, "wrong", user_id=3),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "lesson", "lesson", "certificate"]
        assert [s["lesson_number"] for s in stages if s["key"] == "lesson"] == [1, 2]
        assert [s["label"] for s in stages] == ["Записались", "Урок 1. L1", "Урок 2. L2", "Получили сертификат"]
        assert [s["value"] for s in stages] == [3, 3, 2, 0]

    async def test_lessons_view_monotonic_decreasing(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1), _make_enrollment(course.id, 2)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                _make_submission(course.id, 2, 502, "correct", user_id=2),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        values = [s["value"] for s in resp.json()["stages"]]
        assert values == sorted(values, reverse=True)
        assert values == [2, 2, 1, 0]

    async def test_lessons_view_author_excluded(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all(
            [
                Submission(
                    id=uuid.uuid4(),
                    stepik_submission_id=99,
                    stepik_step_id=500,
                    course_id=course.id,
                    status="correct",
                    submission_time=datetime(2026, 1, 1, tzinfo=UTC),
                    is_author=True,
                ),
                _make_submission(course.id, 98, 502, "correct", user_id=5),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        stages = resp.json()["stages"]
        assert [s["value"] for s in stages] == [1, 1, 1, 0]

    async def test_lessons_view_unattributable_steps_are_skipped(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all([_make_submission(course.id, 1, 999, "correct", user_id=1)])
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        stages = resp.json()["stages"]
        assert [s["value"] for s in stages] == [1, 0, 0, 0]

    async def test_lessons_view_empty_structure(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 999)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        data = resp.json()
        assert [s["key"] for s in data["stages"]] == ["enrolled", "certificate"]
        assert data["stages"][0]["value"] == 1

    async def test_lessons_view_lesson_without_steps_is_kept(self, db_session):
        """Regression: урок без шагов остаётся в воронке (как пустой модуль), нумерация сквозная."""
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await db_session.execute(
            text(
                "INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES "
                "('u3', '12', '1', '2')"
            )
        )
        await db_session.execute(
            text("INSERT INTO raw_lesson (lesson_id, title, steps) VALUES ('12', 'Lempty', :s)"),
            {"s": json.dumps([])},
        )
        db_session.add_all([_make_submission(course.id, 1, 500, "correct", user_id=1)])
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="lessons")
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "lesson", "lesson", "lesson", "certificate"]
        assert [s["lesson_number"] for s in stages if s["key"] == "lesson"] == [1, 2, 3]
        assert [s["label"] for s in stages if s["key"] == "lesson"] == [
            "Урок 1. L1",
            "Урок 2. Lempty",
            "Урок 3. L2",
        ]
        assert [s["value"] for s in stages] == [1, 1, 0, 0, 0]

    async def test_invalid_view_falls_back_to_modules(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course, _make_enrollment(course.id, 1)])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        db_session.add_all([_make_submission(course.id, 1, 500, "correct", user_id=1)])
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id), view="bogus")
        stages = resp.json()["stages"]
        assert [s["key"] for s in stages] == ["enrolled", "module", "module", "certificate"]
        assert [s["label"] for s in stages if s["key"] == "module"] == [
            "Модуль 1. Module A",
            "Модуль 2. Module B",
        ]
