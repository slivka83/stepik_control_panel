"""Тесты эндпоинта GET /api/courses/{course_id}/structure.

Структура курса: модули → уроки → шаги из raw-слоя + статистика submissions.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, Submission, User
from app.services.crypto import encrypt_token

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


def _override_api(db_session, user):
    async def override_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


async def _call(db_session, user, course_id):
    _override_api(db_session, user)
    try:
        return client.get(f"/api/courses/{course_id}/structure")
    finally:
        app.dependency_overrides.clear()


async def _seed_structure(db_session, stepik_course_id=208966):
    """raw-слой: 2 модуля, модуль 1 — 2 урока, модуль 2 — 1 урок."""
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
            "('u1', '10', '1', '1'), ('u2', '11', '1', '2'), ('u3', '12', '2', '1')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO raw_lesson (lesson_id, title, steps) VALUES "
            "('10', 'Lesson A', :s1), ('11', 'Lesson B', :s2), ('12', 'Lesson C', :s3)"
        ),
        {"s1": json.dumps([500, 501]), "s2": json.dumps([502]), "s3": json.dumps([503, 504])},
    )


async def _seed_step_meta(db_session, step_meta):
    """step_meta: step_id → {viewed_by, passed_by, correct_ratio, block, num_grades}."""
    for sid, meta in step_meta.items():
        raw = {"block": {"name": meta.get("block", "text")}}
        if meta.get("viewed_by") is not None:
            raw["viewed_by"] = meta["viewed_by"]
        if meta.get("passed_by") is not None:
            raw["passed_by"] = meta["passed_by"]
        if meta.get("correct_ratio") is not None:
            raw["correct_ratio"] = meta["correct_ratio"]
        if meta.get("num_grades") is not None:
            raw["num_grades"] = meta["num_grades"]
        await db_session.execute(
            text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES (:sid, '10', :raw)"),
            {"sid": str(sid), "raw": json.dumps(raw)},
        )


class TestCourseStructureOwnership:
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


class TestCourseStructureAssembly:
    async def test_empty_structure_returns_empty_modules(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 999)
        db_session.add_all([user, course])
        await db_session.commit()
        resp = await _call(db_session, user, str(course.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["course"]["title"] == course.title
        assert data["modules"] == []

    async def test_modules_lessons_steps_order_and_numbering(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await _seed_step_meta(db_session, {500: {}, 501: {}, 502: {}, 503: {}, 504: {}})
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        assert resp.status_code == 200
        modules = resp.json()["modules"]
        assert [m["position"] for m in modules] == [1, 2]
        assert [m["title"] for m in modules] == ["Module A", "Module B"]

        m1, m2 = modules
        assert [lesson["lesson_number"] for lesson in m1["lessons"]] == [1, 2]
        assert [lesson["title"] for lesson in m1["lessons"]] == ["Lesson A", "Lesson B"]
        assert m2["lessons"][0]["lesson_number"] == 3

        lesson_a = m1["lessons"][0]
        assert [s["step_id"] for s in lesson_a["steps"]] == [500, 501]
        assert [s["step_number"] for s in lesson_a["steps"]] == [1, 2]
        assert [s["lesson_id"] for s in lesson_a["steps"]] == [10, 10]
        assert m1["lessons"][1]["steps"][0]["step_number"] == 1
        assert m2["lessons"][0]["steps"][0]["step_number"] == 1
        assert m2["lessons"][0]["steps"][1]["step_number"] == 2

    async def test_step_meta_from_raw_json_dict(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await _seed_step_meta(
            db_session,
            {500: {"viewed_by": 287, "passed_by": 148, "correct_ratio": 0.9, "block": "code"}},
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        step = resp.json()["modules"][0]["lessons"][0]["steps"][0]
        assert step["block"] == "code"
        assert step["viewed_by"] == 287
        assert step["passed_by"] == 148
        assert abs(step["correct_ratio"] - 0.9) < 1e-9

    async def test_submissions_stats_per_step(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await _seed_step_meta(db_session, {500: {}, 501: {}, 502: {}, 503: {}, 504: {}})
        db_session.add_all(
            [
                _make_submission(course.id, 1, 500, "correct", user_id=1),
                _make_submission(course.id, 2, 500, "wrong", user_id=1),
                _make_submission(course.id, 3, 500, "correct", user_id=2),
                _make_submission(course.id, 4, 502, "wrong", user_id=3),
                _make_submission(course.id, 5, 503, "wrong", user_id=4),
            ]
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        modules = resp.json()["modules"]
        step_500 = modules[0]["lessons"][0]["steps"][0]
        assert step_500["total"] == 3
        assert step_500["correct"] == 2
        assert step_500["students"] == 2
        step_502 = modules[0]["lessons"][1]["steps"][0]
        assert step_502["total"] == 1
        assert step_502["correct"] == 0
        step_504 = modules[1]["lessons"][0]["steps"][1]
        assert step_504["total"] == 0
        assert step_504["correct"] == 0
        assert step_504["students"] == 0

    async def test_author_submissions_excluded(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await _seed_step_meta(db_session, {500: {}})
        db_session.add(
            Submission(
                id=uuid.uuid4(),
                stepik_submission_id=99,
                stepik_step_id=500,
                course_id=course.id,
                status="correct",
                submission_time=datetime(2026, 1, 1, tzinfo=UTC),
                is_author=True,
            )
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        step_500 = resp.json()["modules"][0]["lessons"][0]["steps"][0]
        assert step_500["total"] == 0

    async def test_step_grade_from_num_grades(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await _seed_step_meta(
            db_session,
            {500: {"num_grades": [0, 0, 0, 2, 12]}, 501: {"num_grades": [0, 0, 0, 0, 0]}},
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        lesson_a = resp.json()["modules"][0]["lessons"][0]
        step_500 = lesson_a["steps"][0]
        assert step_500["grade"] == 4.86
        assert step_500["grade_votes"] == 14
        step_501 = lesson_a["steps"][1]
        assert step_501["grade"] is None
        assert step_501["grade_votes"] == 0

    async def test_text_raw_json_string(self, db_session):
        """Regression: SQLite-фикстура хранит _raw_json как TEXT-строку."""
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await _seed_structure(db_session, 208966)
        await db_session.execute(
            text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('500', '10', :raw)"),
            {
                "raw": '{"block": {"name": "video"}, "viewed_by": 10, '
                '"passed_by": 5, "correct_ratio": 0.5, "num_grades": [1, 0, 0, 0, 3]}'
            },
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        step = resp.json()["modules"][0]["lessons"][0]["steps"][0]
        assert step["block"] == "video"
        assert step["viewed_by"] == 10
        assert step["passed_by"] == 5
        assert abs(step["correct_ratio"] - 0.5) < 1e-9
        assert step["grade"] == 4.0
        assert step["grade_votes"] == 4

    async def test_lesson_without_steps(self, db_session):
        user = _make_user()
        course = _make_course(user.id, 208966)
        db_session.add_all([user, course])
        await db_session.commit()
        await db_session.execute(
            text(
                "INSERT INTO raw_section (section_id, course, position, title) "
                "VALUES ('1', :cid, '1', 'Module')"
            ),
            {"cid": "208966"},
        )
        await db_session.execute(
            text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u1', '10', '1', '1')")
        )
        await db_session.execute(
            text("INSERT INTO raw_lesson (lesson_id, title, steps) VALUES ('10', 'Empty', '[]')")
        )
        await db_session.commit()

        resp = await _call(db_session, user, str(course.id))
        lesson = resp.json()["modules"][0]["lessons"][0]
        assert lesson["title"] == "Empty"
        assert lesson["steps"] == []


class TestStepGrade:
    """Юнит-тесты _step_grade — средняя оценка шага из num_grades."""

    def _grade(self, raw):
        from app.api.courses import _step_grade

        return _step_grade(raw)

    def test_weighted_average(self):
        grade, votes = self._grade({"num_grades": [0, 0, 0, 2, 12]})
        assert grade == 4.86
        assert votes == 14

    def test_single_vote(self):
        grade, votes = self._grade({"num_grades": [0, 0, 1, 0, 0]})
        assert grade == 3.0
        assert votes == 1

    def test_all_zero_no_votes(self):
        grade, votes = self._grade({"num_grades": [0, 0, 0, 0, 0]})
        assert grade is None
        assert votes == 0

    def test_missing_field(self):
        grade, votes = self._grade({})
        assert grade is None
        assert votes == 0

    def test_non_list_value(self):
        grade, votes = self._grade({"num_grades": "not-a-list"})
        assert grade is None
        assert votes == 0

    def test_non_numeric_counts_skipped(self):
        grade, votes = self._grade({"num_grades": ["x", 0, 0, 0, 1]})
        assert grade == 5.0
        assert votes == 1

    def test_shorter_list(self):
        grade, votes = self._grade({"num_grades": [0, 1]})
        assert grade == 2.0
        assert votes == 1

    def test_lowest_grade(self):
        grade, votes = self._grade({"num_grades": [3, 0, 0, 0, 0]})
        assert grade == 1.0
        assert votes == 3
