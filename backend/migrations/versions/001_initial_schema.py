"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stepik_id", sa.Integer, unique=True, nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("token_expires_at", sa.DateTime, nullable=False),
        sa.Column("access_level", sa.String, default="Owner"),
        sa.Column("financial_inn", sa.String),
        sa.Column("financial_bik", sa.String),
        sa.Column("taxation_system", sa.String),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer, unique=True, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("status", sa.String, default="Draft"),
        sa.Column("unit_schedule", postgresql.JSONB, default={}),
        sa.Column("content_cache", postgresql.JSONB, default={}),
        sa.Column("health_score", sa.Float, default=100.0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("student_id", sa.Integer, nullable=False),
        sa.Column("student_email", sa.String),
        sa.Column("last_viewed_at", sa.DateTime, nullable=False),
        sa.Column("cohort_status", sa.String, default="Active"),
        sa.Column("is_in_wishlist", sa.Boolean, default=False),
        sa.Column("points_earned", sa.Integer, default=0),
        sa.Column("certificate_issued", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "financial_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_refund", sa.Boolean, default=False),
        sa.Column("transaction_date", sa.DateTime, nullable=False),
        sa.Column("is_b2b", sa.Boolean, default=False),
        sa.Column("ltv_cohort", sa.String),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "competitor_courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("competitor_course_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String),
        sa.Column("rating", sa.Float),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("students_count", sa.Integer),
        sa.Column("snapshot_date", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("competitor_courses")
    op.drop_table("financial_transactions")
    op.drop_table("student_enrollments")
    op.drop_table("courses")
    op.drop_table("users")
