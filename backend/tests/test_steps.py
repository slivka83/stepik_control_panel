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


# ─── wilson_success_pct ─────────────────────────────────────────────────────


class TestWilsonSuccessPct:
    def test_zero_total_returns_zero(self):
        from app.api.dashboard.common import wilson_success_pct

        assert wilson_success_pct(0, 0) == 0.0
        assert wilson_success_pct(10, 0) == 0.0

    def test_small_sample_pulled_down(self):
        from app.api.dashboard.common import wilson_success_pct

        assert round(wilson_success_pct(1, 5), 1) == 3.6

    def test_large_sample_close_to_observed(self):
        from app.api.dashboard.common import wilson_success_pct

        assert round(wilson_success_pct(200, 1000), 1) == 17.6

    def test_zero_success_stays_zero(self):
        from app.api.dashboard.common import wilson_success_pct

        assert wilson_success_pct(0, 50) == 0.0

    def test_success_increases_with_attempts(self):
        """Regression: тот же raw-процент, но больше попыток → выше Wilson."""
        from app.api.dashboard.common import wilson_success_pct

        small = wilson_success_pct(1, 5)
        large = wilson_success_pct(200, 1000)
        assert small < large


class TestWeightedSuccessPct:
    def test_zero_total_returns_zero(self):
        from app.api.dashboard.common import weighted_success_pct

        assert weighted_success_pct(0, 0, 50.0) == 0.0

    def test_small_sample_pulled_to_global(self):
        from app.api.dashboard.common import weighted_success_pct

        assert round(weighted_success_pct(0, 4, 50.0), 1) == 41.7

    def test_large_sample_close_to_observed(self):
        from app.api.dashboard.common import weighted_success_pct

        assert round(weighted_success_pct(100, 400, 50.0), 1) == 26.2

    def test_weighted_keeps_noise_out_of_top(self):
        """Regression: маленький шаг (0%) притянут к среднему и не «самый сложный»."""
        from app.api.dashboard.common import weighted_success_pct

        tiny = weighted_success_pct(0, 4, 50.0)  # 0% → 41.7%
        big = weighted_success_pct(100, 400, 50.0)  # 25% → 27.4%
        assert tiny > big


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
    assert data["steps"][1]["success_pct"] == 9.5
    assert data["steps"][2]["success_pct"] == 34.2


@pytest.mark.asyncio
async def test_hardest_steps_success_weights_attempt_volume(db_session):
    """Regression: «Успех» обязан учитывать объём попыток (Wilson).

    Раньше success_pct = correct/total: шаг с 1 верной попыткой из 5 (20%)
    и шаг со 200 верными из 1000 (20%) показывали одинаковые 20%, хотя это
    разный «успех» — малым объёмом данных верить нельзя. Теперь значение
    занижается сильнее при малых попытках и приближается к наблюдённому при
    больших.
    """
    user = _make_user(55)
    course = _make_course(user.id, 5555)
    rows = []
    for _ in range(4):
        rows.append((601, "wrong"))
    rows.append((601, "correct"))
    for _ in range(800):
        rows.append((602, "wrong"))
    for _ in range(200):
        rows.append((602, "correct"))
    await _seed_user_course_submissions(db_session, user, course, rows=rows)

    data = await _get_steps(db_session, user, min_submissions=1)

    by_id = {s["stepik_step_id"]: s for s in data["steps"]}
    small = by_id[601]  # 1/5 → 20% raw
    large = by_id[602]  # 200/1000 → 20% raw

    assert small["total"] == 5 and small["correct"] == 1
    assert large["total"] == 1000 and large["correct"] == 200
    assert small["success_pct"] == 3.6
    assert large["success_pct"] == 17.6
    assert small["success_pct"] < large["success_pct"]


@pytest.mark.asyncio
async def test_hardest_steps_weighted_success_keeps_noise_out_of_top(db_session):
    """Regression: «Взвешенный успех» не даёт шагам с 1-2 попытками лезть в топ.

    Раньше топ «Самых сложных» занимали шаги с мизерным числом попыток
    (0% при 1 попытке). Взвешенный успех притягивает малообъёмные шаги к
    среднему по автору, и настоящая проблема (много попыток + низкий
    успех) остаётся в топе.
    """
    user = _make_user(56)
    course = _make_course(user.id, 5566)
    rows = []
    for _ in range(4):
        rows.append((611, "wrong"))  # 0/4 — маленький шаг, 0% успеха
    for _ in range(300):
        rows.append((612, "wrong"))  # 100/400 — большой шаг, 25%
    for _ in range(100):
        rows.append((612, "correct"))
    for _ in range(10):
        rows.append((613, "wrong"))  # 90/100 — хороший шаг
    for _ in range(90):
        rows.append((613, "correct"))
    await _seed_user_course_submissions(db_session, user, course, rows=rows)

    data = await _get_steps(db_session, user, min_submissions=1)

    by_id = {s["stepik_step_id"]: s for s in data["steps"]}
    tiny = by_id[611]  # 0/4 → wilson 0.0, weighted притянут к среднему
    big = by_id[612]  # 100/400 → wilson 22.5, weighted ≈ 25.6
    good = by_id[613]  # 90/100 → wilson 82.7, weighted ≈ 81.4

    assert "weighted_success_pct" in tiny and "weighted_success_pct" in big
    # Малый шаг не должен быть «самым сложным»: его взвешенный успех выше
    # реальной проблемы (big), хотя по raw-проценту/Успеху он выглядит хуже
    assert tiny["success_pct"] == 0.0
    assert tiny["weighted_success_pct"] > big["weighted_success_pct"]
    assert good["weighted_success_pct"] > big["weighted_success_pct"]
    assert data["steps"][0]["stepik_step_id"] == 612


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


@pytest.mark.asyncio
async def test_hardest_steps_module_and_lesson_numbers(db_session):
    """Regression: «Шаг» показывает путь модуль.урок-шаг (3.7-2).

    Глобальный номер урока считается сквозь курс: сумма уроков предыдущих
    модулей + номер внутри своего модуля. Без этого шаг из 3-го модуля
    показывал бы номер урока «внутри модуля» вместо номера на Stepik.
    """
    user = _make_user(12)
    course = _make_course(user.id, 1212)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(500, "wrong"), (501, "wrong"), (500, "correct")],
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES
            (500, 11, '{}'),
            (501, 12, '{}')
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_lesson (lesson_id, steps, title, _raw_json) VALUES
            (10, '[5010]', 'Урок 1', '{}'),
            (11, '[500, 5001]', 'Урок 2', '{}'),
            (12, '[501]', 'Урок 3', '{}')
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_section (section_id, course, position, units, title, _raw_json) VALUES
            (100, 1212, '1', '[2010, 2011]', 'Модуль 1', '{}'),
            (200, 1212, '2', '[2012]', 'Модуль 2', '{}')
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO raw_unit (unit_id, lesson_id, section_id, position, _raw_json) VALUES
            (2010, 10, 100, '1', '{}'),
            (2011, 11, 100, '2', '{}'),
            (2012, 12, 200, '1', '{}')
        """)
    )
    await db_session.commit()

    data = await _get_steps(db_session, user, min_submissions=1)

    by_id = {s["stepik_step_id"]: s for s in data["steps"]}
    assert by_id[500]["module_number"] == 1
    assert by_id[500]["lesson_number"] == 2  # 1-й модуль, 2-й урок
    assert by_id[500]["module_title"] == "Модуль 1"
    assert by_id[500]["lesson_title"] == "Урок 2"
    assert by_id[501]["module_number"] == 2
    assert by_id[501]["lesson_number"] == 3  # сквозной счёт: 2 урока в модуле 1 + 1
    assert by_id[501]["module_title"] == "Модуль 2"
    assert by_id[501]["lesson_title"] == "Урок 3"


@pytest.mark.asyncio
async def test_hardest_steps_module_lesson_missing_returns_none(db_session):
    """Шаг без записи в raw_unit/raw_section — module_number/lesson_number None."""
    user = _make_user(13)
    course = _make_course(user.id, 1313)
    await _seed_user_course_submissions(
        db_session, user, course,
        rows=[(520, "wrong")],
    )

    data = await _get_steps(db_session, user, min_submissions=1)

    for s in data["steps"]:
        assert "module_number" in s and s["module_number"] is None
        assert "lesson_number" in s and s["lesson_number"] is None
        assert "module_title" in s and s["module_title"] is None
        assert "lesson_title" in s and s["lesson_title"] is None
