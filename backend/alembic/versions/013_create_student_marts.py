"""create student_marts view layer

Revision ID: 013
Revises: 20fc60296db6
Create Date: 2026-08-01

Витрина студентов: одна строка на студента автора. Пересобирается
трансформацией в конце синка из student_enrollments, submissions,
raw_comment и raw_user. API /students читает только её — без прямых
запросов к сырому слою.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "013"
down_revision = "20fc60296db6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_marts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("cohort_status", sa.String(), nullable=True),
        sa.Column("courses_count", sa.Integer(), nullable=False),
        sa.Column("certificates", sa.Integer(), nullable=False),
        sa.Column("submissions_count", sa.Integer(), nullable=False),
        sa.Column("submissions_successful", sa.Integer(), nullable=False),
        sa.Column("comments_count", sa.Integer(), nullable=False),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", name="uq_student_marts_student_id"),
    )
    op.create_index("ix_student_marts_student_id", "student_marts", ["student_id"])
    op.create_index("ix_student_marts_last_activity", "student_marts", ["last_activity"])


def downgrade() -> None:
    op.drop_index("ix_student_marts_last_activity", table_name="student_marts")
    op.drop_index("ix_student_marts_student_id", table_name="student_marts")
    op.drop_table("student_marts")
