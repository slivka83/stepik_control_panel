"""Тесты эндпоинта /api/dashboard/reviews/stats.

Покрытие: месячные/годовые/по-курсовые агрегаты, средняя оценка (avg_score),
distinct-студенты, фильтр по курсам (course_ids, пустой выбор, чужие курсы),
инвариант «фильтр = все курсы» == «без фильтра», пустые данные.
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

client = TestClient(app, raise_server_exceptions=False)


def _make_user() -> User:
    return User(
        id=uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )


async def _seed(db, user, with_reviews=True):
    """Два своих курса (stepik 100/200) + чужой (300)."""
    db.add(user)
    await db.flush()

    c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
    c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="Java", status="Published")
    db.add_all([c1, c2])
    await db.flush()

    if with_reviews:
        reviews = [
            # course 100: июль, 3 отзыва: оценки 5, 4 и без score; авторы 1, 2, 3
            ("r1", "1", "100", {"create_date": "2026-07-10T10:00:00Z", "score": 5, "user": 1}),
            ("r2", "2", "100", {"create_date": "2026-07-11T10:00:00Z", "score": 4, "user": 2}),
            ("r3", "3", "100", {"create_date": "2026-07-12T10:00:00Z", "user": 3}),
            # course 200: август, 1 отзыв score 3, автор 1; ревью с не-числовым user_id — в students не входит
            ("r4", "1", "200", {"create_date": "2026-08-01T10:00:00Z", "score": 3, "user": 1}),
            ("r5", "stepik_panel", "200", {"create_date": "2026-08-02T10:00:00Z", "score": 5, "user": "stepik_panel"}),
            # без create_date → пропускается
            ("r6", "4", "100", {"score": 1, "user": 4}),
        ]
        for rid, uid, course, payload in reviews:
            await db.execute(
                text('INSERT INTO raw_course_review (review_id, "user", course, _raw_json) '
                     "VALUES (:rid, :uid, :course, :j)"),
                {"rid": rid, "uid": uid, "course": course, "j": json.dumps(payload)},
            )
    await db.flush()
    return c1, c2


def _override_api(db, user):
    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


def _get_stats(db, user, **params):
    _override_api(db, user)
    try:
        return client.get("/api/dashboard/reviews/stats", params=params).json()
    finally:
        app.dependency_overrides.clear()


async def test_reviews_aggregates_months_years_courses(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_stats(db_session, user)

    months = {m["month"]: m for m in data["months"]}
    july = months["Июль 2026"]
    assert july == {"month": "Июль 2026", "students": 3, "total": 3, "avg_score": 4.5}
    aug = months["Август 2026"]
    assert aug == {"month": "Август 2026", "students": 1, "total": 2, "avg_score": 4.0}

    assert data["years"] == [{"year": 2026, "students": 3, "total": 5, "avg_score": 4.25}]

    assert data["totals"] == {"reviews": 5, "students": 3, "avg_score": 4.25}

    by_course = {b["stepik_course_id"]: b for b in data["by_course"]}
    assert by_course[100] == {
        "course_id": str(c1.id), "stepik_course_id": 100, "title": "Python",
        "students": 3, "total": 3, "avg_score": 4.5,
    }
    assert by_course[200] == {
        "course_id": str(c2.id), "stepik_course_id": 200, "title": "Java",
        "students": 1, "total": 2, "avg_score": 4.0,
    }


async def test_reviews_empty_db(db_session):
    user = _make_user()
    await _seed(db_session, user, with_reviews=False)
    data = _get_stats(db_session, user)
    assert data == {
        "months": [], "years": [], "by_course": [],
        "totals": {"reviews": 0, "students": 0, "avg_score": 0},
    }


async def test_reviews_course_filter_restricts(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_stats(db_session, user, course_ids=str(c1.id))
    assert data["totals"] == {"reviews": 3, "students": 3, "avg_score": 4.5}
    assert [b["stepik_course_id"] for b in data["by_course"]] == [100]
    assert [m["month"] for m in data["months"]] == ["Июль 2026"]

    data2 = _get_stats(db_session, user, course_ids=f"{c1.id},{c2.id}")
    data3 = _get_stats(db_session, user)
    assert data2["totals"] == data3["totals"]
    assert data2["months"] == data3["months"]
    assert data2["by_course"] == data3["by_course"]


async def test_reviews_empty_selection_returns_empty(db_session):
    user = _make_user()
    await _seed(db_session, user)
    data = _get_stats(db_session, user, course_ids="")
    assert data["totals"] == {"reviews": 0, "students": 0, "avg_score": 0}
    assert data["months"] == []


async def test_reviews_foreign_course_excluded(db_session):
    """Чужие курсы увидеть нельзя — даже если их отзывы в raw-слое."""
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
        text('INSERT INTO raw_course_review (review_id, "user", course, _raw_json) '
             "VALUES ('r_foreign', '5', '300', :j)"),
        {"j": json.dumps({"create_date": "2026-07-01T10:00:00Z", "score": 2})},
    )

    data = _get_stats(db_session, user)
    assert data["totals"]["reviews"] == 5
    assert data["totals"]["students"] == 3
