"""Тесты эндпоинта hardest-steps и его хелперов.

Regression: step_number не вычислялся на live PostgreSQL — raw_lesson.steps
там jsonb, asyncpg отдаёт уже разобранный list, а код вызывал
json.loads(list) → TypeError → молча пустой результат (синий текст без
ссылки на шаг в UI). SQLite-фикстура (TEXT-колонка) баг не воспроизводила.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.api.dashboard.steps import _parse_step_positions
from app.database import get_db
from app.main import app
from app.models import Course, Submission, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


def _make_user(stepik_id: int) -> User:
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


def _call_endpoint(**params):
    return client.get("/api/dashboard/hardest-steps", params=params).json()


async def _get_steps(db_session, user, **params):
    """Вызвать эндпоинт с оверрайдами и гарантированно их снять."""
    _override_api(db_session, user)
    try:
        return _call_endpoint(**params)
    finally:
        app.dependency_overrides.clear()


async def _seed_user_course_submissions(db_session, user, course, rows):
    db_session.add(user)
    db_session.add(course)
    await db_session.flush()
    for i, (step, status) in enumerate(rows):
        db_session.add(_make_submission(course.id, 7000 + i, step, status))
    await db_session.commit()


# ─── _parse_step_positions: jsonb (list) vs TEXT (str) ──────────────────────


class TestParseStepPositions:
    def test_jsonb_list_from_live_pg(self):
        """Regression: asyncpg возвращает jsonb-колонку как Python list."""
        raw = [9215905, 10141395, 10141397, 10474775, 10141403, 10141402, 10141404]
        assert _parse_step_positions(raw) == {
            9215905: 1,
            10141395: 2,
            10141397: 3,
            10474775: 4,
            10141403: 5,
            10141402: 6,
            10141404: 7,
        }

    def test_text_string_from_sqlite_fixture(self):
        """TEXT-колонка отдаёт JSON-строку — тоже обязана работать."""
        raw = json.dumps([9215905, 10141395, 10141397])
        assert _parse_step_positions(raw) == {9215905: 1, 10141395: 2, 10141397: 3}

    def test_empty_list(self):
        assert _parse_step_positions([]) == {}

    def test_none(self):
        assert _parse_step_positions(None) == {}

    def test_non_json_string(self):
        assert _parse_step_positions("not-json-at-all") == {}

    def test_string_with_garbage_tail_ignored(self):
        assert _parse_step_positions(" [10, 20] trailing") == {}

    def test_dict_input_returns_empty(self):
        """jsonb-объект (не массив) — позиций нет."""
        assert _parse_step_positions({"10": 1}) == {}

    def test_string_ids_are_converted(self):
        """В jsonb могут лежать числа; строковые id тоже конвертируются."""
        assert _parse_step_positions(["10", 20]) == {10: 1, 20: 2}

    def test_unparseable_entries_skipped_not_crash(self):
        """Позиция = индекс в массиве, а не счётчик разобранных."""
        assert _parse_step_positions([1, None, "abc", 4]) == {1: 1, 4: 4}

    def test_first_element_is_position_one(self):
        """Позиция 1-based: первый шаг урока → /step/1."""
        assert _parse_step_positions([777]) == {777: 1}

    def test_large_realistic_lesson(self):
        raw = list(range(1000, 1100))
        result = _parse_step_positions(raw)
        assert result[1000] == 1
        assert result[1099] == 100
        assert len(result) == 100

    def test_duplicates_keep_last_position(self):
        assert _parse_step_positions([5, 5, 7]) == {5: 2, 7: 3}


# ─── Полный эндпоинт на SQLite-фикстуре ────────────────────────────────────


@pytest.mark.asyncio
async def test_hardest_steps_returns_lesson_and_step_number(db_session):
    """Regression: каждый шаг обязан получить lesson_id и step_number."""
    user = _make_user(1)
    course = _make_course(user.id, 101)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(500, "wrong"), (501, "wrong"), (500, "correct")],
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES
            (500, 10, '{}'),
            (501, 11, '{}')
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_lesson (lesson_id, steps, _raw_json) VALUES
            (10, '[500]', '{}'),
            (11, '[501]', '{}')
        """)
    )
    await db_session.commit()

    data = await _get_steps(db_session, user, min_submissions=1)

    by_id = {s["stepik_step_id"]: s for s in data["steps"]}
    assert 500 in by_id and 501 in by_id
    assert by_id[500]["lesson_id"] == 10
    assert by_id[500]["step_number"] == 1
    assert by_id[501]["lesson_id"] == 11
    assert by_id[501]["step_number"] == 1


@pytest.mark.asyncio
async def test_hardest_steps_position_from_lesson_steps_order(db_session):
    """Номер шага — это позиция в списке шагов урока, а не порядок ответов."""
    user = _make_user(2)
    course = _make_course(user.id, 202)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(500, "wrong"), (501, "wrong"), (500, "correct")],
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES
            (500, 10, '{}'),
            (501, 10, '{}')
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_lesson (lesson_id, steps, _raw_json) VALUES
            (10, '[501, 500]', '{}')
        """)
    )
    await db_session.commit()

    data = await _get_steps(db_session, user, min_submissions=1)

    by_id = {s["stepik_step_id"]: s for s in data["steps"]}
    assert by_id[501]["lesson_id"] == 10
    assert by_id[501]["step_number"] == 1
    assert by_id[500]["lesson_id"] == 10
    assert by_id[500]["step_number"] == 2


@pytest.mark.asyncio
async def test_hardest_steps_no_lesson_no_step_number(db_session):
    """Шаг без записи в raw_step — поля None, но ключи присутствуют."""
    user = _make_user(3)
    course = _make_course(user.id, 303)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(500, "wrong")],
    )

    data = await _get_steps(db_session, user, min_submissions=1)

    assert data["steps"]
    for s in data["steps"]:
        assert "lesson_id" in s and s["lesson_id"] is None
        assert "step_number" in s and s["step_number"] is None


@pytest.mark.asyncio
async def test_hardest_steps_empty_db(db_session):
    user = _make_user(4)
    db_session.add(user)
    await db_session.commit()

    data = await _get_steps(db_session, user)

    assert data == {"steps": []}


@pytest.mark.asyncio
async def test_hardest_steps_orders_worst_first(db_session):
    """Сортировка по success asc: худшие сверху."""
    user = _make_user(5)
    course = _make_course(user.id, 505, title="Bad")
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(900, "wrong"), (901, "correct"), (901, "wrong"), (902, "correct"), (902, "correct")],
    )

    data = await _get_steps(db_session, user, min_submissions=1)

    ids = [s["stepik_step_id"] for s in data["steps"]]
    assert ids == [900, 901, 902]
    assert data["steps"][0]["success_pct"] == 0.0
    assert data["steps"][1]["success_pct"] == 50.0
    assert data["steps"][2]["success_pct"] == 100.0


@pytest.mark.asyncio
async def test_hardest_steps_respects_min_submissions(db_session):
    user = _make_user(6)
    course = _make_course(user.id, 606)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(910, "wrong")],
    )

    data_loose = await _get_steps(db_session, user, min_submissions=1)
    assert [s["stepik_step_id"] for s in data_loose["steps"]] == [910]

    data_strict = await _get_steps(db_session, user, min_submissions=2)
    assert data_strict["steps"] == []


@pytest.mark.asyncio
async def test_hardest_steps_excludes_author_submissions(db_session):
    """Отправки автора не считаются (is_author)."""
    user = _make_user(7)
    course = _make_course(user.id, 707)
    db_session.add(user)
    db_session.add(course)
    await db_session.flush()
    db_session.add(
        Submission(
            id=uuid.uuid4(),
            stepik_submission_id=9001,
            stepik_step_id=920,
            course_id=course.id,
            status="correct",
            submission_time=datetime(2026, 1, 1, tzinfo=UTC),
            is_author=True,
        )
    )
    await db_session.commit()

    data = await _get_steps(db_session, user, min_submissions=1)

    assert data["steps"] == []


@pytest.mark.asyncio
async def test_hardest_steps_limit(db_session):
    user = _make_user(8)
    course = _make_course(user.id, 808)
    rows = [(step, "wrong") for step in range(1000, 1010)]
    await _seed_user_course_submissions(db_session, user, course, rows=rows)

    data = await _get_steps(db_session, user, min_submissions=1, limit=3)

    assert len(data["steps"]) == 3


@pytest.mark.asyncio
async def test_hardest_steps_only_own_courses(db_session):
    """Чужие курсы (другого пользователя) не попадают в выдачу."""
    owner = _make_user(9)
    db_session.add(owner)
    await db_session.flush()
    course_own = _make_course(owner.id, 909)
    db_session.add(course_own)
    await db_session.flush()

    stranger = _make_user(10)
    course_other = _make_course(stranger.id, 1010)
    await _seed_user_course_submissions(
        db_session, stranger, course_other,
        rows=[(950, "wrong")],
    )
    db_session.add(_make_submission(course_own.id, 9500, 951, "wrong"))
    await db_session.commit()

    data = await _get_steps(db_session, owner, min_submissions=1)

    ids = [s["stepik_step_id"] for s in data["steps"]]
    assert ids == [951]


@pytest.mark.asyncio
async def test_hardest_steps_counts_distinct_students(db_session):
    """students = количество уникальных user_id в группировке по шагу."""
    user = _make_user(11)
    course = _make_course(user.id, 1111)
    db_session.add(user)
    db_session.add(course)
    await db_session.flush()

    steps_rows = [
        (960, "wrong", 800),
        (960, "correct", 800),
        (960, "wrong", 801),
        (961, "correct", 801),
    ]
    for i, (step, status, uid) in enumerate(steps_rows):
        db_session.add(_make_submission(course.id, 9600 + i, step, status, user_id=uid))
    await db_session.commit()

    data = await _get_steps(db_session, user, min_submissions=1)

    by_step = {s["stepik_step_id"]: s for s in data["steps"]}
    assert by_step[960]["total"] == 3
    assert by_step[960]["students"] == 2
    assert by_step[961]["total"] == 1
    assert by_step[961]["students"] == 1
    for s in data["steps"]:
        assert s["course_title"] == "Python 101"
