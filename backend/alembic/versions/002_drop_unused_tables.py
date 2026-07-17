"""drop unused tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("competitor_courses")
    op.drop_table("financial_transactions")


def downgrade() -> None:
    op.create_table(
        "financial_transactions",
        op.Column("id", op.String(36), primary_key=True),
        op.Column("course_id", op.String(36), nullable=False),
        op.Column("amount", op.Numeric(10, 2), nullable=False),
        op.Column("is_refund", op.Boolean, default=False),
        op.Column("transaction_date", op.DateTime, nullable=False),
        op.Column("is_b2b", op.Boolean, default=False),
        op.Column("ltv_cohort", op.String),
        op.Column("created_at", op.DateTime),
    )
    op.create_table(
        "competitor_courses",
        op.Column("id", op.String(36), primary_key=True),
        op.Column("user_id", op.String(36), nullable=False),
        op.Column("competitor_course_id", op.Integer, nullable=False),
        op.Column("title", op.String),
        op.Column("rating", op.Float),
        op.Column("price", op.Numeric(10, 2)),
        op.Column("students_count", op.Integer),
        op.Column("snapshot_date", op.DateTime, nullable=False),
        op.Column("created_at", op.DateTime),
    )
