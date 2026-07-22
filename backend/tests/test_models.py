import uuid
from datetime import datetime, timezone

import pytest

from app.models import User, Course, StudentEnrollment, Submission, FinancialSnapshot


@pytest.mark.asyncio
async def test_user_creation(db_session):
    user = User(
        stepik_id=12345,
        access_token="encrypted_access",
        refresh_token="encrypted_refresh",
        token_expires_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    result = await db_session.get(User, user.id)
    assert result is not None
    assert result.stepik_id == 12345
    assert result.access_level == "Owner"
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_user_unique_stepik_id(db_session):
    user1 = User(stepik_id=999, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    user2 = User(stepik_id=999, access_token="b", refresh_token="r2", token_expires_at=datetime.now(timezone.utc))
    db_session.add(user1)
    db_session.add(user2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_course_creation(db_session):
    user = User(stepik_id=123, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    db_session.add(user)
    await db_session.commit()

    course = Course(
        user_id=user.id,
        stepik_course_id=100,
        title="Test Course",
    )
    db_session.add(course)
    await db_session.commit()
    result = await db_session.get(Course, course.id)
    assert result is not None
    assert result.title == "Test Course"
    assert result.status == "Draft"
    assert result.health_score == 100.0


@pytest.mark.asyncio
async def test_course_relationship(db_session):
    user = User(stepik_id=123, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    db_session.add(user)
    await db_session.commit()

    course = Course(user_id=user.id, stepik_course_id=100, title="Test")
    db_session.add(course)
    await db_session.commit()

    await db_session.refresh(user)
    assert len(user.courses) == 1
    assert user.courses[0].title == "Test"


@pytest.mark.asyncio
async def test_enrollment_creation(db_session):
    user = User(stepik_id=123, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    db_session.add(user)
    await db_session.commit()

    course = Course(user_id=user.id, stepik_course_id=100, title="Test")
    db_session.add(course)
    await db_session.commit()

    enrollment = StudentEnrollment(
        course_id=course.id,
        student_id=200,
        last_viewed_at=datetime.now(timezone.utc),
    )
    db_session.add(enrollment)
    await db_session.commit()
    result = await db_session.get(StudentEnrollment, enrollment.id)
    assert result is not None
    assert result.student_id == 200
    assert result.cohort_status == "Active"
    assert result.points_earned == 0
    assert result.certificate_issued is False


@pytest.mark.asyncio
async def test_submission_creation(db_session):
    user = User(stepik_id=123, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    db_session.add(user)
    await db_session.commit()

    course = Course(user_id=user.id, stepik_course_id=100, title="Test")
    db_session.add(course)
    await db_session.commit()

    submission = Submission(
        course_id=course.id,
        step_id=500,
        student_id=200,
        status="correct",
        submission_time=datetime.now(timezone.utc),
    )
    db_session.add(submission)
    await db_session.commit()
    result = await db_session.get(Submission, submission.id)
    assert result is not None
    assert result.status == "correct"
    assert result.step_id == 500


@pytest.mark.asyncio
async def test_financial_snapshot_creation(db_session):
    snapshot = FinancialSnapshot(
        data={"summary": {"total": 100}, "months": []},
    )
    db_session.add(snapshot)
    await db_session.commit()
    result = await db_session.get(FinancialSnapshot, snapshot.id)
    assert result is not None
    assert result.data["summary"]["total"] == 100
    assert result.updated_at is not None


def test_user_repr():
    user = User(stepik_id=1, access_token="a", refresh_token="r", token_expires_at=datetime.now(timezone.utc))
    assert "User id=" in repr(user)
    assert "stepik_id=1" in repr(user)


def test_course_repr():
    course = Course(title="Test")
    assert "Course id=" in repr(course)
    assert "'Test'" in repr(course)
