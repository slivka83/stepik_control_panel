"""drop unused columns

Revision ID: 003
Revises: 002
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("courses", "unit_schedule")
    op.drop_column("courses", "content_cache")
    op.drop_column("student_enrollments", "student_email")
    op.drop_column("student_enrollments", "is_in_wishlist")


def downgrade() -> None:
    op.add_column("courses", sa.Column("unit_schedule", JSONB, default={}))
    op.add_column("courses", sa.Column("content_cache", JSONB, default={}))
    op.add_column("student_enrollments", sa.Column("student_email", sa.String, nullable=True))
    op.add_column("student_enrollments", sa.Column("is_in_wishlist", sa.Boolean, default=False))
