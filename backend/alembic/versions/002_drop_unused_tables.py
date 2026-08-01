"""drop unused tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("competitor_courses")
    op.drop_table("financial_transactions")


def downgrade() -> None:
    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_refund", sa.Boolean, default=False),
        sa.Column("transaction_date", sa.DateTime, nullable=False),
        sa.Column("is_b2b", sa.Boolean, default=False),
        sa.Column("ltv_cohort", sa.String),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_table(
        "competitor_courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("competitor_course_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String),
        sa.Column("rating", sa.Float),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("students_count", sa.Integer),
        sa.Column("snapshot_date", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime),
    )
