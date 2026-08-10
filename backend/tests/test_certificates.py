"""Тесты эндпоинта /api/dashboard/certificates/stats.

Покрытие: месячные/годовые/по-курсовые агрегаты, разбивка «С отличием»
(distinction) vs «Обычные» (regular), distinct-студенты, фильтр по курсам
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

client = TestClient(app, raise_server_exceptions=False)


def _make_user() -> User:
    return User(
        id=uuid.uuid4(),
        stepik_id=12345,
        access_token=encrypt_token("token"),
        refresh_token=encrypt_token("refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )


async def _seed(db, user, with_certs=True):
    """Два своих курса (stepik 100/200) + чужой (300)."""
    db.add(user)
    await db.flush()

    c1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
    c2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="Java", status="Published")
    db.add_all([c1, c2])
    await db.flush()

    if with_certs:
        certs = [
            # course 100: июль, 2 сертификата: distinction + regular, авторы 1 и 2
            ("c1", "1", "100", {"issue_date": "2026-07-10T10:00:00Z", "type": "distinction", "user": 1}),
            ("c2", "2", "100", {"issue_date": "2026-07-11T10:00:00Z", "type": "regular", "user": 2}),
            # course 200: август, 1 regular, автор 1; distinction с не-числовым user_id — в students не входит
            ("c3", "1", "200", {"issue_date": "2026-08-01T10:00:00Z", "type": "regular", "user": 1}),
            ("c4", "stepik_panel", "200", {"issue_date": "2026-08-02T10:00:00Z", "type": "distinction", "user": "stepik_panel"}),
            # без type → обычные; без issue_date → пропускается
            ("c5", "3", "100", {"issue_date": "2026-07-15T10:00:00Z", "user": 3}),
            ("c6", "4", "100", {"type": "regular", "user": 4}),
        ]
        for cid, uid, course, payload in certs:
            await db.execute(
                text("INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json) "
                     "VALUES (:cid, :uid, :course, :j)"),
                {"cid": cid, "uid": uid, "course": course, "j": json.dumps(payload)},
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
        return client.get("/api/dashboard/certificates/stats", params=params).json()
    finally:
        app.dependency_overrides.clear()


async def test_certificates_aggregates_months_years_courses(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_stats(db_session, user)

    months = {m["month"]: m for m in data["months"]}
    july = months["Июль 2026"]
    assert july == {"month": "Июль 2026", "students": 3, "total": 3, "distinction": 1, "regular": 2}
    aug = months["Август 2026"]
    assert aug == {"month": "Август 2026", "students": 1, "total": 2, "distinction": 1, "regular": 1}

    assert data["years"] == [{"year": 2026, "students": 3, "total": 5, "distinction": 2, "regular": 3}]

    assert data["totals"] == {"certificates": 5, "students": 3, "distinction": 2, "regular": 3}

    by_course = {b["stepik_course_id"]: b for b in data["by_course"]}
    assert by_course[100] == {
        "course_id": str(c1.id), "stepik_course_id": 100, "title": "Python",
        "students": 3, "total": 3, "distinction": 1, "regular": 2,
    }
    assert by_course[200] == {
        "course_id": str(c2.id), "stepik_course_id": 200, "title": "Java",
        "students": 1, "total": 2, "distinction": 1, "regular": 1,
    }


async def test_certificates_empty_db(db_session):
    user = _make_user()
    await _seed(db_session, user, with_certs=False)
    data = _get_stats(db_session, user)
    assert data == {
        "months": [], "years": [], "by_course": [],
        "totals": {"certificates": 0, "students": 0, "distinction": 0, "regular": 0},
    }


async def test_certificates_course_filter_restricts(db_session):
    user = _make_user()
    c1, c2 = await _seed(db_session, user)

    data = _get_stats(db_session, user, course_ids=str(c1.id))
    assert data["totals"] == {"certificates": 3, "students": 3, "distinction": 1, "regular": 2}
    assert [b["stepik_course_id"] for b in data["by_course"]] == [100]
    assert [m["month"] for m in data["months"]] == ["Июль 2026"]

    data2 = _get_stats(db_session, user, course_ids=f"{c1.id},{c2.id}")
    data3 = _get_stats(db_session, user)
    assert data2["totals"] == data3["totals"]
    assert data2["months"] == data3["months"]
    assert data2["by_course"] == data3["by_course"]


async def test_certificates_empty_selection_returns_empty(db_session):
    user = _make_user()
    await _seed(db_session, user)
    data = _get_stats(db_session, user, course_ids="")
    assert data["totals"] == {"certificates": 0, "students": 0, "distinction": 0, "regular": 0}
    assert data["months"] == []


async def test_certificates_foreign_course_excluded(db_session):
    """Чужие курсы увидеть нельзя — даже если их сертификаты в raw-слое."""
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
        text("INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json) "
             "VALUES ('c_foreign', '5', '300', :j)"),
        {"j": json.dumps({"issue_date": "2026-07-01T10:00:00Z", "type": "regular"})},
    )

    data = _get_stats(db_session, user)
    assert data["totals"]["certificates"] == 5
    assert data["totals"]["students"] == 3
