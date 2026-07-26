"""add is_author column to submissions

Revision ID: 007
Revises: 006
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("is_author", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("submissions", "is_author")
