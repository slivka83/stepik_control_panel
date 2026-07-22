"""add submissions table

Revision ID: 004
Revises: 003
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("step_id", sa.Integer, nullable=False),
        sa.Column("student_id", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("submission_time", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_submissions_course_id", "submissions", ["course_id"])
    op.create_index("ix_submissions_step_id", "submissions", ["step_id"])
    op.create_index("ix_submissions_student_id", "submissions", ["student_id"])
    op.create_index("ix_submissions_status", "submissions", ["status"])


def downgrade() -> None:
    op.drop_table("submissions")
