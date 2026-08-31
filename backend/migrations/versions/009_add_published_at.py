"""add published_at column to courses

Revision ID: 009
Revises: 008
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("courses", "published_at")
