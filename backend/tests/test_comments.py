"""Тесты эндпоинта /api/dashboard/comments.

Покрытие: месячные/годовые/по-курсовые агрегаты, distinct-студенты,
лайки/дизлайки из vote_delta, ответы из reply_count, фильтр по курсам
(course_ids, пустой выбор, чужие курсы), инвариант «фильтр = все курсы»
== «без фильтра», пустые данные.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, User
from app.services.crypto import encrypt_token
from tests.conftest import build_marts

client = TestClient(app, raise_server_exceptions=False)


def _make_user() -> User:
    return User(
        id=uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )


async def _seed(db, user, with_comments=True):
    """Два своих курса (stepik 100/200) + чужой (300) со структурой шагов."""
    db.add(user)
    await db.flush()

    c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
    c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="Java", status="Published")
    db.add_all([c1, c2])
    await db.flush()

    await db.execute(text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('2', '100', '1', 'M1')"))
    await db.execute(text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('3', '200', '1', 'M2')"))
    await db.execute(text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u5', '10', '2', '1')"))
    await db.execute(text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u6', '11', '3', '1')"))
    await db.execute(text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('500', '10', :j)"), {"j": "{}"})
    await db.execute(text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('501', '11', :j)"), {"j": "{}"})
    await db.execute(
        text("INSERT INTO raw_lesson (lesson_id, steps, title) VALUES ('10', :s, 'L1')"),
        {"s": json.dumps(["500"])},
    )
    await db.execute(
        text("INSERT INTO raw_lesson (lesson_id, steps, title) VALUES ('11', :s, 'L2')"),
        {"s": json.dumps(["501"])},
    )
    await db.execute(
        text("INSERT INTO raw_user (user_id, first_name, last_name) VALUES ('1', 'Иван', 'Петров')"),
    )

    if with_comments:
        comments = [
            # course 100: +3 лайка, -1 дизлайк, 1 ответ; авторы 1 и 2 (июль)
            ("c1", {"id": 1, "user": 1, "target": 500, "time": "2026-07-10T10:00:00Z", "vote_delta": 3, "reply_count": 1, "text": "<p>Вопрос <b>по лекции</b></p>"}),
            ("c2", {"id": 2, "user": 2, "target": 500, "time": "2026-07-11T10:00:00Z", "vote_delta": -1, "reply_count": 0, "text": "<p>Дизлайк</p>"}),
            # не-числовой автор — в students не считается, но в total/лайках да
            ("c3", {"id": 3, "user": "stepik_panel", "target": 500, "time": "2026-07-12T10:00:00Z", "vote_delta": 1, "reply_count": 0, "text": "<p>OAuth-клиент</p>"}),
            # course 200: 2 ответа, автор 1 (август)
            ("c4", {"id": 4, "user": 1, "target": 501, "time": "2026-08-01T10:00:00Z", "vote_delta": 0, "reply_count": 2, "text": "<p>Без оценок</p>"}),
            # шаг вне структуры (не атрибутируется ни к одному курсу) — пропускается
            ("c5", {"id": 5, "user": 9, "target": 9999, "time": "2026-07-20T10:00:00Z", "vote_delta": 7, "reply_count": 0, "text": "<p>Вне курсов</p>"}),
        ]
        for cid, payload in comments:
            await db.execute(
                text('INSERT INTO raw_comment (comment_id, "user", target, "time", _raw_json) '
                     "VALUES (:cid, :u, :t, :tm, :j)"),
                {"cid": cid, "u": str(payload["user"]), "t": str(payload["target"]),
                 "tm": payload["time"], "j": json.dumps(payload)},
            )
    await db.flush()
    await build_marts(db)
    return c1, c2


def _override_api(db, user):
    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


def _get_comments(db, user, **params):
    _override_api(db, user)
    try:
        return client.get("/api/dashboard/comments", params=params).json()
    finally:
        app.dependency_overrides.clear()


def _get_list(db, user, **params):
    _override_api(db, user)
    try:
        return client.get("/api/dashboard/comments/list", params=params).json()
    finally:
        app.dependency_overrides.clear()


async def test_comments_aggregates_months_years_courses(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_comments(db_session, user)

    months = {m["month"]: m for m in data["months"]}
    july = months["Июль 2026"]
    assert july == {"month": "Июль 2026", "students": 2, "total": 3, "likes": 4, "dislikes": 1, "replies": 1}
    aug = months["Август 2026"]
    assert aug == {"month": "Август 2026", "students": 1, "total": 1, "likes": 0, "dislikes": 0, "replies": 2}

    assert data["years"] == [{"year": 2026, "students": 2, "total": 4, "likes": 4, "dislikes": 1, "replies": 3}]

    assert data["totals"] == {"comments": 4, "students": 2, "likes": 4, "dislikes": 1, "replies": 3}

    by_course = {b["stepik_course_id"]: b for b in data["by_course"]}
    assert by_course[100] == {
        "course_id": str(c1.id), "stepik_course_id": 100, "title": "Python",
        "students": 2, "total": 3, "likes": 4, "dislikes": 1, "replies": 1,
    }
    assert by_course[200] == {
        "course_id": str(c2.id), "stepik_course_id": 200, "title": "Java",
        "students": 1, "total": 1, "likes": 0, "dislikes": 0, "replies": 2,
    }


async def test_comments_empty_db(db_session):
    user = _make_user()
    await _seed(db_session, user, with_comments=False)
    data = _get_comments(db_session, user)
    assert data == {
        "months": [], "years": [], "by_course": [],
        "totals": {"comments": 0, "students": 0, "likes": 0, "dislikes": 0, "replies": 0},
    }


async def test_comments_course_filter_restricts(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_comments(db_session, user, course_ids=str(c1.id))
    assert data["totals"] == {"comments": 3, "students": 2, "likes": 4, "dislikes": 1, "replies": 1}
    assert [b["stepik_course_id"] for b in data["by_course"]] == [100]
    assert [m["month"] for m in data["months"]] == ["Июль 2026"]

    data2 = _get_comments(db_session, user, course_ids=f"{c1.id},{c2.id}")
    data3 = _get_comments(db_session, user)
    assert data2["totals"] == data3["totals"]
    assert data2["months"] == data3["months"]
    assert data2["by_course"] == data3["by_course"]


async def test_comments_empty_selection_returns_empty(db_session):
    user = _make_user()
    await _seed(db_session, user)
    data = _get_comments(db_session, user, course_ids="")
    assert data["totals"] == {"comments": 0, "students": 0, "likes": 0, "dislikes": 0, "replies": 0}
    assert data["months"] == []


async def test_comments_foreign_course_excluded(db_session):
    """Чужие курсы увидеть нельзя — даже если шаги их комментариев в raw-слое."""
    user = _make_user()
    c1, _ = await _seed(db_session, user)

    other = User(
        id=uuid.uuid4(), stepik_id=999,
        access_token=encrypt_token("t"), refresh_token=encrypt_token("t"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    db_session.add(other)
    await db_session.flush()
    await db_session.execute(
        text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('4', '300', '1', 'M3')")
    )
    await db_session.execute(
        text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u7', '12', '4', '1')")
    )
    await db_session.execute(text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('502', '12', :j)"), {"j": "{}"})
    await db_session.execute(
        text('INSERT INTO raw_comment (comment_id, "user", target, "time", _raw_json) '
             "VALUES ('c_foreign', '5', '502', '2026-07-01T10:00:00Z', :j)"),
        {"j": json.dumps({"user": 5, "target": 502, "time": "2026-07-01T10:00:00Z", "vote_delta": 10, "reply_count": 0})},
    )

    # фильтр по чужому курсу → пусто
    data = _get_comments(db_session, user, course_ids=str(c1.id))
    assert data["totals"]["comments"] == 3


# ─── /comments/list (вкладки «Не отвеченные» и «Дизлайки») ────────────────


async def test_comments_list_unanswered_basics(db_session):
    """unanswered: is_staff_replied != true, user_role != teacher, не-атрибутируемые пропускаются."""
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_list(db_session, user, type="unanswered")
    assert data["total"] == 4
    rows = {r["comment_id"]: r for r in data["comments"]}

    c = rows[1]
    assert c["time"] == "2026-07-10T10:00:00Z"
    assert c["user_id"] == 1
    assert c["user_name"] == "Иван Петров"
    assert c["course_id"] == str(c1.id)
    assert c["course_title"] == "Python"
    assert c["stepik_course_id"] == 100
    assert c["text"] == "Вопрос по лекции"  # HTML вырезан
    assert c["likes"] == 3
    assert c["dislikes"] == 0
    assert c["replies"] == 1
    # путь шага: модуль M1, урок 1, шаг 1 → "1.1-1"
    assert c["module_number"] == 1
    assert c["lesson_number"] == 1
    assert c["step_number"] == 1
    assert c["module_title"] == "M1"
    assert c["lesson_title"] == "L1"
    assert c["lesson_id"] == 10

    # не-числовой автор (OAuth-клиент) — user_name None, но в списке есть
    assert rows[3]["user_name"] is None

    # курс 200
    assert rows[4]["course_id"] == str(c2.id)
    assert rows[4]["module_title"] == "M2"
    assert rows[4]["stepik_course_id"] == 200


async def test_comments_list_unanswered_excludes_replied_teacher_deleted(db_session):
    """unanswered: is_staff_replied=true, user_role=teacher, is_deleted — исключаются."""
    user = _make_user()
    await _seed(db_session, user)
    extra = [
        ("c10", {"id": 10, "user": 1, "target": 500, "time": "2026-07-01T10:00:00Z",
                 "vote_delta": 1, "reply_count": 0, "is_staff_replied": True}),
        ("c11", {"id": 11, "user": 7, "target": 500, "time": "2026-07-02T10:00:00Z",
                 "vote_delta": 1, "reply_count": 0, "user_role": "teacher"}),
        ("c12", {"id": 12, "user": 8, "target": 500, "time": "2026-07-03T10:00:00Z",
                 "vote_delta": 1, "reply_count": 0, "is_deleted": True}),
    ]
    for cid, payload in extra:
        await db_session.execute(
            text('INSERT INTO raw_comment (comment_id, "user", target, "time", _raw_json) '
                 "VALUES (:cid, :u, :t, :tm, :j)"),
            {"cid": cid, "u": str(payload["user"]), "t": str(payload["target"]),
             "tm": payload["time"], "j": json.dumps(payload)},
        )
    await db_session.flush()

    data = _get_list(db_session, user, type="unanswered")
    ids = {r["comment_id"] for r in data["comments"]}
    assert 10 not in ids  # автор ответил
    assert 11 not in ids  # комментарий учителя
    assert 12 not in ids  # удалён
    assert data["total"] == 4


async def test_comments_list_disliked(db_session):
    """disliked: только vote_delta < 0."""
    user = _make_user()
    await _seed(db_session, user)

    data = _get_list(db_session, user, type="disliked")
    assert data["total"] == 1
    c = data["comments"][0]
    assert c["comment_id"] == 2
    assert c["dislikes"] == 1
    assert c["likes"] == 0


async def test_comments_list_course_filter_and_invariant(db_session):
    """Фильтр по курсам сужает список; «все курсы» == «без фильтра»."""
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_list(db_session, user, type="unanswered", course_ids=str(c1.id))
    assert data["total"] == 3
    assert {r["stepik_course_id"] for r in data["comments"]} == {100}

    data2 = _get_list(db_session, user, type="unanswered", course_ids=f"{c1.id},{c2.id}")
    data3 = _get_list(db_session, user, type="unanswered")
    assert data2["total"] == data3["total"]
    assert [r["comment_id"] for r in data2["comments"]] == [r["comment_id"] for r in data3["comments"]]

    empty = _get_list(db_session, user, type="unanswered", course_ids="")
    assert empty == {"comments": [], "total": 0}


async def test_comments_list_sort_and_pagination(db_session):
    """Сортировка time/asc + NULLS LAST, пагинация skip/limit + total."""
    user = _make_user()
    await _seed(db_session, user)

    data = _get_list(db_session, user, type="unanswered", sort="time", order="asc", limit=2)
    assert data["total"] == 4
    assert len(data["comments"]) == 2
    # asc → самые старые сверху (c4 → август первым? нет: июль раньше августа)
    times = [r["time"] for r in data["comments"]]
    assert times == sorted(times)

    page2 = _get_list(db_session, user, type="unanswered", sort="time", order="asc", skip=2, limit=2)
    assert len(page2["comments"]) == 2
    assert [r["comment_id"] for r in data["comments"]] != [r["comment_id"] for r in page2["comments"]]

    desc = _get_list(db_session, user, type="unanswered", sort="time", order="desc")
    assert desc["comments"][0]["time"] > desc["comments"][-1]["time"]


async def test_comments_list_invalid_params(db_session):
    user = _make_user()
    await _seed(db_session, user)
    _override_api(db_session, user)
    try:
        assert client.get("/api/dashboard/comments/list", params={"type": "bogus"}).status_code == 400
        assert client.get("/api/dashboard/comments/list", params={"sort": "bogus"}).status_code == 400
        assert client.get("/api/dashboard/comments/list", params={"order": "sideways"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


async def test_comments_list_empty_db(db_session):
    user = _make_user()
    await _seed(db_session, user, with_comments=False)
    assert _get_list(db_session, user, type="unanswered") == {"comments": [], "total": 0}
    assert _get_list(db_session, user, type="disliked") == {"comments": [], "total": 0}
