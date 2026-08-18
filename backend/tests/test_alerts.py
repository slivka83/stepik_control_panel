import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import get_user
from app.database import get_db
from app.main import app
from app.models import Course, StudentEnrollment, User
from app.services.crypto import encrypt_token

client = TestClient(app, raise_server_exceptions=False)


async def _seed_user(session):
    user = User(
        id=uuid.uuid4(),
        stepik_id=64381531,
        access_token=encrypt_token("test_access"),
        refresh_token=encrypt_token("test_refresh"),
        token_expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()
    return user


async def _run(db_session, user, courses_enrollments):
    """courses_enrollments: list of (stepik_id, title, [(points, cert_issued), ...])."""
    async def override_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_user] = override_user
    try:
        for stepik_id, title, students in courses_enrollments:
            course = Course(
                id=uuid.uuid4(),
                user_id=user.id,
                stepik_course_id=stepik_id,
                title=title,
                status="Published",
            )
            db_session.add(course)
            await db_session.flush()
            for i, (points, cert) in enumerate(students):
                db_session.add(
                    StudentEnrollment(
                        id=uuid.uuid4(),
                        course_id=course.id,
                        student_id=stepik_id * 1000 + i,
                        last_viewed_at=datetime.now(UTC).replace(tzinfo=None),
                        points_earned=points,
                        certificate_issued=cert,
                    )
                )
        await db_session.commit()
        response = client.get("/api/dashboard/alerts")
        assert response.status_code == 200
        return response.json()["alerts"]
    finally:
        app.dependency_overrides.clear()


class TestAlertsBoundaries:
    async def test_points_exactly_100_triggers_cert_alert(self, db_session):
        user = await _seed_user(db_session)
        alerts = await _run(db_session, user, [(123, "ML", [(100, False)])])
        warnings = [a for a in alerts if "сертификат" in a["message"]]
        assert len(warnings) == 1

    async def test_certificate_issued_true_excluded(self, db_session):
        user = await _seed_user(db_session)
        # passed the threshold but already got the certificate → no alert
        alerts = await _run(db_session, user, [(123, "ML", [(150, True)])])
        warnings = [a for a in alerts if "сертификат" in a["message"]]
        assert len(warnings) == 0

    async def test_low_score_exactly_10_excluded(self, db_session):
        user = await _seed_user(db_session)
        alerts = await _run(db_session, user, [(456, "JS", [(0, False)] * 10)])
        errors = [a for a in alerts if a["type"] == "error"]
        assert len(errors) == 0

    async def test_low_score_exactly_11_included(self, db_session):
        user = await _seed_user(db_session)
        alerts = await _run(db_session, user, [(456, "JS", [(0, False)] * 11)])
        errors = [a for a in alerts if a["type"] == "error"]
        assert len(errors) == 1
        assert "11 студентов" in errors[0]["message"]

    async def test_both_warning_and_error_present(self, db_session):
        user = await _seed_user(db_session)
        alerts = await _run(
            db_session,
            user,
            [
                (123, "ML", [(100, False)] * 5),  # warning
                (456, "JS", [(0, False)] * 11),  # error
            ],
        )
        warnings = [a for a in alerts if "сертификат" in a["message"]]
        errors = [a for a in alerts if a["type"] == "error"]
        assert len(warnings) == 1
        assert len(errors) == 1
        assert len(alerts) == 2
