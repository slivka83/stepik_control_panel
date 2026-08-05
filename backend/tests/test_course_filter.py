"""Course-filter tests: ?course_ids= restricts every dashboard/financials
endpoint to a subset of the author's courses.

Covered: parse_course_ids, security (foreign courses dropped), SQL-backed
endpoints (submissions, active students, cohorts, alerts, hardest steps,
students list), snapshot-backed recomputation (financials, revenue, kpi,
published solutions, community), and the invariant «filter = all courses»
== «no filter».
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.auth import get_user
from app.api.dashboard.common import get_courses_for_user
from app.api.dashboard.course_filter import parse_course_ids
from app.constants import MONTH_NAMES
from app.database import get_db
from app.main import app
from app.models import Course, FinancialSnapshot, StudentEnrollment, StudentMart, Submission, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


def _now():
    """Current time (second precision) — cohorts endpoint uses full-precision now."""
    return datetime.now(UTC).replace(microsecond=0)


async def _seed_scenario(session):
    """Two owned courses (stepik 100/200) + one foreign course (300)."""
    user = User(
        id=uuid.uuid4(),
        stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    other = User(
        id=uuid.uuid4(),
        stepik_id=999,
        access_token=encrypt_token("t"),
        refresh_token=encrypt_token("t"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    session.add_all([user, other])
    await session.flush()

    u1 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=100, title="Python", status="Published")
    u2 = Course(id=uuid.uuid4(), user_id=user.id, stepik_course_id=200, title="Java", status="Published")
    u3 = Course(id=uuid.uuid4(), user_id=other.id, stepik_course_id=300, title="Foreign", status="Published")
    session.add_all([u1, u2, u3])
    await session.flush()

    now = _now()

    submissions = [
        (1, 500, u1.id, 1, "correct"),
        (2, 500, u1.id, 2, "wrong"),
        (3, 500, u1.id, 3, "correct"),
        (4, 501, u2.id, 4, "correct"),
    ]
    for sid, step, cid, uid, status in submissions:
        session.add(
            Submission(
                id=uuid.uuid4(),
                stepik_submission_id=sid,
                stepik_step_id=step,
                course_id=cid,
                status=status,
                user_id=uid,
                submission_time=now,
                is_author=False,
            )
        )
    await session.flush()

    enrollments = [
        (u1.id, 1, now, now, 50, False),
        (u1.id, 2, now, now, 100, True),
        (u2.id, 4, now - timedelta(days=15), now, 120, False),
    ]
    for cid, sid, lv, dj, points, cert in enrollments:
        session.add(
            StudentEnrollment(
                id=uuid.uuid4(),
                course_id=cid,
                student_id=sid,
                last_viewed_at=lv,
                date_joined=dj,
                points_earned=points,
                certificate_issued=cert,
            )
        )
    for sid in (1, 2, 4):
        session.add(
            StudentMart(
                id=uuid.uuid4(),
                student_id=sid,
                name=f"S{sid}",
                cohort_status="Active",
                last_activity=now,
            )
        )
    await session.flush()

    await session.execute(
        text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('500', '10', :j)"),
        {"j": json.dumps({"num_grades": [0, 0, 0, 2, 12]})},
    )
    await session.execute(
        text("INSERT INTO raw_step (step_id, lesson, _raw_json) VALUES ('501', '11', :j)"),
        {"j": json.dumps({"num_grades": [1, 1, 1, 1, 1]})},
    )
    await session.execute(
        text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u5', '10', '2', '1')")
    )
    await session.execute(
        text("INSERT INTO raw_unit (unit_id, lesson_id, section_id, position) VALUES ('u6', '11', '3', '1')")
    )
    await session.execute(
        text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('2', '100', '1', 'Module 1')")
    )
    await session.execute(
        text("INSERT INTO raw_section (section_id, course, position, title) VALUES ('3', '200', '1', 'Module 2')")
    )

    cur_key = f"{now.year}-{now.month:02d}"
    t1 = (now - timedelta(days=2)).replace(tzinfo=None).isoformat() + "Z"
    comments = [
        ("c1", "500", "", "Обычный комментарий"),
        ("c2", "500", "solution", "Решение"),
        ("c3", "501", "", "Комментарий java"),
    ]
    for cid_, target, thread, body in comments:
        await session.execute(
            text(
                "INSERT INTO raw_comment (comment_id, \"user\", target, \"time\", thread, _raw_json) "
                "VALUES (:cid, '1', :t, :tm, :th, :j)"
            ),
            {
                "cid": cid_,
                "t": target,
                "tm": t1,
                "th": thread,
                "j": json.dumps({"target": int(target), "time": t1, "thread": thread, "text": body}),
            },
        )
    await session.execute(
        text("INSERT INTO raw_certificate (certificate_id, user_id, course_id, _raw_json) VALUES ('cert1', '1', '100', :j)"),
        {"j": json.dumps({"issue_date": cur_key + "-15T10:00:00Z"})},
    )
    await session.execute(
        text("INSERT INTO raw_course_review (review_id, course, _raw_json) VALUES ('rev1', '100', :j)"),
        {"j": json.dumps({"create_date": cur_key + "-10T10:00:00Z"})},
    )

    month_label = f"{MONTH_NAMES.get(now.month, str(now.month))} {now.year}"
    t_p = (now - timedelta(days=2)).replace(tzinfo=None).isoformat() + "Z"
    raw_payments = [
        {"id": 1, "course": 100, "status": "paid", "amount": 1000, "payment_amount": 1000, "time": t_p, "promo_code": "PROMO1", "last_course_click_utm": {"utm_source": "yandex_stpk"}},
        {"id": 2, "course": 100, "status": "refunded", "amount": 200, "payment_amount": 200, "time": t_p, "promo_code": None, "last_course_click_utm": {"utm_source": "stepik_telegram"}},
        {"id": 3, "course": 200, "status": "paid", "amount": 5000, "payment_amount": 5000, "time": t_p, "promo_code": "PROMO2", "last_course_click_utm": {"utm_source": "yandex_stpk"}},
    ]
    recent_payments = [
        {
            "id": b["id"],
            "course": "Python" if b["course"] == 100 else "Java",
            "amount": float(b["amount"]),
            "payment_amount": float(b["payment_amount"]),
            "status": b["status"],
            "time": b["time"],
            "raw": b,
        }
        for b in raw_payments
    ]
    snapshot_data = {
        "summary": {
            "total_turnover": 5800,
            "total_income": 6000,
            "total_refunds": 200,
            "total_payments": 3,
            "total_refunds_count": 1,
            "net_income": 5800,
            "current_month_turnover": 5800,
            "current_month_income": 6000,
            "current_month_payments": 3,
        },
        "months": [
            {
                "month": month_label,
                "year": now.year,
                "month_num": now.month,
                "turnover": 5800,
                "income": 6000,
                "refunds": 200,
                "payments_count": 3,
                "refunds_count": 1,
            }
        ],
        "courses": [
            {"course_id": 200, "title": "Java", "price": 5000, "turnover": 5000, "income": 5000, "refunds": 0, "payments": 1},
            {"course_id": 100, "title": "Python", "price": 1000, "turnover": 800, "income": 1000, "refunds": 200, "payments": 2},
        ],
        "promos": [
            {"promo_code": "PROMO1", "payments": 1, "turnover": 1000, "income": 1000, "refunds": 0, "last_used": t_p},
            {"promo_code": "PROMO2", "payments": 1, "turnover": 5000, "income": 5000, "refunds": 0, "last_used": t_p},
        ],
        "utms": [
            {"utm_source": "Я.Директ", "payments": 2, "turnover": 6000, "income": 6000, "refunds": 0, "last_used": t_p},
            {"utm_source": "Telegram", "payments": 1, "turnover": 0, "income": 0, "refunds": 200, "last_used": t_p},
        ],
        "recent_payments": recent_payments,
        "community": {
            "average_rating": 3.75,
            "total_reviews": 3,
            "total_comments": 3,
            "comments_monthly": {cur_key: 3},
            "total_solutions": 1,
            "solutions_monthly": {cur_key: 1},
            "per_course": {
                "100": {"comments": 2, "reviews_count": 2, "average_rating": 4.5},
                "200": {"comments": 1, "reviews_count": 1, "average_rating": 3.0},
            },
        },
    }
    session.add(
        FinancialSnapshot(id=uuid.uuid4(), data=snapshot_data, updated_at=now.replace(tzinfo=None))
    )
    await session.commit()
    return user, u1, u2, u3


def _override(user, db_session):
    async def override_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user


class TestParseCourseIds:
    def test_parse_none_or_empty(self):
        assert parse_course_ids(None) is None
        assert parse_course_ids("") == []
        assert parse_course_ids(" , ") == []

    def test_parse_invalid_dropped(self):
        u1 = uuid.uuid4()
        assert parse_course_ids(f"{u1},garbage,not-a-uuid") == [u1]
        assert parse_course_ids("garbage") == []

    def test_parse_list(self):
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        assert parse_course_ids(f"{u1},{u2}") == [u1, u2]


class TestFilterSecurity:
    async def test_foreign_course_dropped(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        courses, ids = await get_courses_for_user(db_session, user, [u1.id, u3.id])
        assert ids == [u1.id]

    async def test_endpoint_ignores_foreign_course(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/submissions?course_ids={u3.id}")
            assert response.status_code == 200
            assert response.json() == {"months": [], "by_course": [], "years": []}

            response = client.get(f"/api/dashboard/kpi?course_ids={u3.id}")
            assert response.status_code == 200
            assert response.json()["total_students"] == 0
            assert response.json()["courses_count"] == 0
        finally:
            app.dependency_overrides.clear()


class TestFilterSubmissions:
    async def test_submissions_filtered_to_course(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/submissions?course_ids={u1.id}")
            data = response.json()
            assert len(data["months"]) == 1
            assert data["months"][0]["total"] == 3
            assert data["months"][0]["correct"] == 2
            assert data["months"][0]["students"] == 3
            assert len(data["by_course"]) == 1
            assert data["by_course"][0]["stepik_course_id"] == 100
            assert data["by_course"][0]["title"] == "Python"
            assert data["years"][0]["total"] == 3
        finally:
            app.dependency_overrides.clear()

    async def test_empty_course_ids_param_means_nothing_selected(self, db_session):
        """?course_ids= (пусто) — явно ничего не выбрано: пустой дашборд."""
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get("/api/dashboard/submissions?course_ids=")
            assert response.json() == {"months": [], "by_course": [], "years": []}

            response = client.get("/api/dashboard/kpi?course_ids=")
            data = response.json()
            assert data["total_students"] == 0
            assert data["courses_count"] == 0

            response = client.get("/api/dashboard/students?course_ids=")
            assert response.json()["total"] == 0
        finally:
            app.dependency_overrides.clear()


class TestFilterActiveStudents:
    async def test_active_students_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/active-students?course_ids={u1.id}")
            months = response.json()["months"]
            assert months[0]["dark"] == 3
            assert months[0]["light"] == 3

            response = client.get("/api/dashboard/active-students")
            months = response.json()["months"]
            assert months[0]["dark"] == 4
            assert months[0]["light"] == 4
        finally:
            app.dependency_overrides.clear()

    async def test_active_enrolled_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/active-enrolled-students?course_ids={u1.id}")
            months = response.json()["months"]
            assert months[0]["dark"] == 2
            assert months[0]["light"] == 2
        finally:
            app.dependency_overrides.clear()


class TestFilterCohorts:
    async def test_cohorts_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/cohorts?course_ids={u1.id}")
            data = response.json()
            assert data["active"] == 2
            assert data["passive"] == 0
            assert data["fading"] == 0
            assert data["sleeping"] == 0

            response = client.get(f"/api/dashboard/cohorts?course_ids={u2.id}")
            data = response.json()
            assert data["active"] == 0
            assert data["passive"] == 1
        finally:
            app.dependency_overrides.clear()


class TestFilterAlerts:
    async def test_alerts_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/alerts?course_ids={u2.id}")
            assert response.status_code == 200
            assert len(response.json()["alerts"]) == 1

            response = client.get(f"/api/dashboard/alerts?course_ids={u1.id}")
            assert response.json()["alerts"] == []
        finally:
            app.dependency_overrides.clear()


class TestFilterHardestSteps:
    async def test_hardest_steps_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/hardest-steps?course_ids={u1.id}&min_submissions=1")
            steps = response.json()["steps"]
            assert len(steps) == 1
            assert steps[0]["stepik_step_id"] == 500
            assert steps[0]["course_title"] == "Python"
            assert steps[0]["total"] == 3
        finally:
            app.dependency_overrides.clear()


class TestFilterStudents:
    async def test_students_filtered_by_enrollment(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/students?course_ids={u1.id}")
            data = response.json()
            assert data["total"] == 2
            assert {s["student_id"] for s in data["students"]} == {1, 2}

            response = client.get("/api/dashboard/students")
            assert response.json()["total"] == 3
        finally:
            app.dependency_overrides.clear()


class TestFilterFinancials:
    async def test_financials_recomputed_for_course(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        cur_key = f"{_now().year}-{_now().month:02d}"
        _override(user, db_session)
        try:
            response = client.get(f"/api/financials?course_ids={u1.id}")
            data = response.json()
            assert data["summary"]["total_turnover"] == 800
            assert data["summary"]["total_income"] == 1000
            assert data["summary"]["total_refunds"] == 200
            assert data["summary"]["total_payments"] == 2
            assert data["summary"]["total_refunds_count"] == 1
            assert data["summary"]["net_income"] == 800

            assert len(data["months"]) == 1
            m = data["months"][0]
            assert m["payments_count"] == 2
            assert m["refunds_count"] == 1
            assert m["turnover"] == 800
            assert m["income"] == 1000
            assert m["refunds"] == 200

            assert len(data["courses"]) == 1
            assert data["courses"][0]["course_id"] == 100
            assert data["courses"][0]["title"] == "Python"
            assert data["courses"][0]["price"] == 1000
            assert data["courses"][0]["payments"] == 2

            assert len(data["recent_payments"]) == 2
            assert all(p["raw"]["course"] == 100 for p in data["recent_payments"])

            promos = {p["promo_code"]: p for p in data["promos"]}
            assert set(promos) == {"PROMO1"}
            assert promos["PROMO1"]["turnover"] == 1000

            utms = {u["utm_source"]: u for u in data["utms"]}
            assert set(utms) == {"Я.Директ", "Telegram"}
            assert utms["Я.Директ"]["turnover"] == 1000
            assert utms["Telegram"]["refunds"] == 200

            community = data["community"]
            assert community["total_comments"] == 2
            assert community["comments_monthly"][cur_key] == 2
            assert community["total_solutions"] == 1
            assert community["solutions_monthly"][cur_key] == 1
            assert community["total_reviews"] == 2
            assert community["average_rating"] == 4.5
            assert community["per_course"] == {"100": {"comments": 2, "reviews_count": 2, "average_rating": 4.5}}
        finally:
            app.dependency_overrides.clear()

    async def test_filter_all_courses_equals_no_filter(self, db_session):
        """Инвариант: выбор всех курсов == отсутствие фильтра (сверка с глобальным снапшотом)."""
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            no_filter = client.get("/api/financials")
            both = client.get(f"/api/financials?course_ids={u1.id},{u2.id}")
            assert both.status_code == 200
            assert both.json() == no_filter.json()

            kpi_all = client.get("/api/dashboard/kpi")
            kpi_both = client.get(f"/api/dashboard/kpi?course_ids={u1.id},{u2.id}")
            assert kpi_both.json() == kpi_all.json()
        finally:
            app.dependency_overrides.clear()


class TestFilterCharts:
    async def test_revenue_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/revenue?course_ids={u1.id}")
            months = response.json()["months"]
            assert len(months) == 1
            assert months[0]["income"] == 1000
            assert months[0]["turnover"] == 800
        finally:
            app.dependency_overrides.clear()

    async def test_published_solutions_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/published-solutions?course_ids={u1.id}")
            months = response.json()["months"]
            assert len(months) == 1
            assert months[0]["dark"] == 1
            assert months[0]["light"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_certificates_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        now = _now()
        total = now.year * 12 + now.month - 2
        old_year, old_month = (total - 1) // 12, (total - 1) % 12 + 1
        old_key = f"{old_year}-{old_month:02d}"
        certs = [
            ("x1", "100", old_key, "distinction"),
            ("x2", "100", old_key, "regular"),
            ("x3", "200", old_key, "regular"),
            ("x4", "300", old_key, "distinction"),
        ]
        for cid_, course, issue, ctype in certs:
            await db_session.execute(
                text(
                    "INSERT INTO raw_certificate (certificate_id, course_id, _raw_json) "
                    "VALUES (:cid, :course, :j)"
                ),
                {"cid": cid_, "course": course, "j": json.dumps({"issue_date": issue + "-15T10:00:00Z", "type": ctype})},
            )
        await db_session.commit()
        _override(user, db_session)
        try:
            label = f"{MONTH_NAMES[old_month]} {old_year}"
            response = client.get(f"/api/dashboard/certificates?course_ids={u1.id}")
            months = response.json()["months"]
            assert len(months) == 2, "cert1 из сценария (текущий месяц) + 2 добавленных"
            by_label = {m["month"]: m for m in months}
            assert by_label[label] == {"month": label, "dark": 2, "light": 1}

            response = client.get(f"/api/dashboard/certificates?course_ids={u2.id}")
            months = response.json()["months"]
            assert months == [{"month": label, "dark": 1, "light": 1}]

            response = client.get(f"/api/dashboard/certificates?course_ids={u3.id}")
            assert response.json()["months"] == [], "чужой курс не отдаёт сертификаты"

            response = client.get("/api/dashboard/certificates?course_ids=")
            assert response.json()["months"] == [], "пустой выбор = нет данных"
        finally:
            app.dependency_overrides.clear()


class TestFilterKPI:
    async def test_kpi_filtered(self, db_session):
        user, u1, u2, u3 = await _seed_scenario(db_session)
        _override(user, db_session)
        try:
            response = client.get(f"/api/dashboard/kpi?course_ids={u1.id}")
            data = response.json()
            assert data["courses_count"] == 1
            assert data["courses_published"] == 1
            assert data["total_students"] == 2
            assert data["certificates_issued"] == 1
            assert data["current_month_submissions"] == 3
            assert data["current_month_students"] == 2
            assert data["total_income"] == 1000
            assert data["current_month_turnover"] == 800
            assert data["total_comments"] == 2
            assert data["total_reviews"] == 2
            assert data["average_rating"] == 4.5
            assert data["certificates_current_month"] == 1
            assert data["reviews_current_month"] == 1
            assert data["published_solutions_current_month"] == 1
            expected_grade = (4 * 2 + 5 * 12) / 14
            assert data["steps_average_grade"] == round(expected_grade, 2)
        finally:
            app.dependency_overrides.clear()
