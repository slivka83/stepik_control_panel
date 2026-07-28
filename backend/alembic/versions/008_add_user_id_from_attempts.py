"""add user_id column from attempts

Revision ID: 008
Revises: 007
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "user_id")
