"""add indexes, unique constraint, timezone columns

Revision ID: 005
Revises: 004
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_users_stepik_id", "users", ["stepik_id"])
    op.create_index("ix_courses_user_id", "courses", ["user_id"])
    op.create_index("ix_student_enrollments_course_id", "student_enrollments", ["course_id"])
    op.create_index("ix_student_enrollments_student_id", "student_enrollments", ["student_id"])
    op.create_index("ix_student_enrollments_last_viewed", "student_enrollments", ["last_viewed_at"])
    op.create_index("ix_student_enrollments_course_student", "student_enrollments", ["course_id", "student_id"])
    op.create_unique_constraint("uq_enrollment", "student_enrollments", ["course_id", "student_id"])

    for table in ["users", "courses", "student_enrollments", "submissions", "financial_snapshots"]:
        for col in ["created_at", "updated_at", "token_expires_at", "last_viewed_at", "submission_time"]:
            try:
                op.alter_column(table, col, type_=sa.DateTime(timezone=True))
            except Exception:
                pass


def downgrade() -> None:
    for table in ["users", "courses", "student_enrollments", "submissions", "financial_snapshots"]:
        for col in ["created_at", "updated_at", "token_expires_at", "last_viewed_at", "submission_time"]:
            try:
                op.alter_column(table, col, type_=sa.DateTime(timezone=False))
            except Exception:
                pass

    op.drop_constraint("uq_enrollment", "student_enrollments", type_="unique")
    op.drop_index("ix_student_enrollments_course_student", "student_enrollments")
    op.drop_index("ix_student_enrollments_last_viewed", "student_enrollments")
    op.drop_index("ix_student_enrollments_student_id", "student_enrollments")
    op.drop_index("ix_student_enrollments_course_id", "student_enrollments")
    op.drop_index("ix_courses_user_id", "courses")
    op.drop_index("ix_users_stepik_id", "users")
