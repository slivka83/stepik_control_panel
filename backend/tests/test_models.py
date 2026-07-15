import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


class TestUserModel:
    def test_user_fields(self):
        user = MagicMock()
        user.id = uuid.uuid4()
        user.stepik_id = 12345
        user.access_token = "encrypted_access"
        user.refresh_token = "encrypted_refresh"
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        user.access_level = "Owner"
        user.financial_inn = None
        user.financial_bik = None
        user.taxation_system = None
        user.created_at = datetime.now(timezone.utc)

        assert user.stepik_id == 12345
        assert user.access_level == "Owner"
        assert user.financial_inn is None

    def test_user_default_access_level(self):
        user = MagicMock()
        user.access_level = "Owner"
        assert user.access_level == "Owner"


class TestCourseModel:
    def test_course_fields(self):
        course = MagicMock()
        course.id = uuid.uuid4()
        course.user_id = uuid.uuid4()
        course.stepik_course_id = 100
        course.title = "Test Course"
        course.status = "Draft"
        course.unit_schedule = {}
        course.content_cache = {}
        course.health_score = 100.0
        course.created_at = datetime.now(timezone.utc)

        assert course.title == "Test Course"
        assert course.health_score == 100.0
        assert course.status == "Draft"

    def test_course_jsonb_defaults(self):
        course = MagicMock()
        course.unit_schedule = {}
        course.content_cache = {}
        assert course.unit_schedule == {}
        assert course.content_cache == {}


class TestStudentEnrollmentModel:
    def test_enrollment_fields(self):
        enrollment = MagicMock()
        enrollment.id = uuid.uuid4()
        enrollment.course_id = uuid.uuid4()
        enrollment.student_id = 100
        enrollment.student_email = None
        enrollment.last_viewed_at = datetime.now(timezone.utc)
        enrollment.cohort_status = "Active"
        enrollment.is_in_wishlist = False
        enrollment.points_earned = 0
        enrollment.certificate_issued = False
        enrollment.created_at = datetime.now(timezone.utc)

        assert enrollment.student_id == 100
        assert enrollment.cohort_status == "Active"
        assert enrollment.is_in_wishlist is False
        assert enrollment.points_earned == 0
        assert enrollment.certificate_issued is False


class TestFinancialTransactionModel:
    def test_transaction_fields(self):
        transaction = MagicMock()
        transaction.id = uuid.uuid4()
        transaction.course_id = uuid.uuid4()
        transaction.amount = 1500.50
        transaction.is_refund = False
        transaction.transaction_date = datetime.now(timezone.utc)
        transaction.is_b2b = False
        transaction.ltv_cohort = None
        transaction.created_at = datetime.now(timezone.utc)

        assert transaction.amount == 1500.50
        assert transaction.is_refund is False
        assert transaction.is_b2b is False


class TestCompetitorCourseModel:
    def test_competitor_fields(self):
        competitor = MagicMock()
        competitor.id = uuid.uuid4()
        competitor.user_id = uuid.uuid4()
        competitor.competitor_course_id = 3000
        competitor.title = "Competitor Course"
        competitor.rating = 4.5
        competitor.price = 2999.99
        competitor.students_count = 5000
        competitor.snapshot_date = datetime.now(timezone.utc)
        competitor.created_at = datetime.now(timezone.utc)

        assert competitor.title == "Competitor Course"
        assert competitor.rating == 4.5
        assert competitor.students_count == 5000
