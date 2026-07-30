"""drop health_score from courses

Revision ID: 010
Revises: 009
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("courses", "health_score")


def downgrade() -> None:
    op.add_column("courses", sa.Column("health_score", sa.Float, default=100.0))
