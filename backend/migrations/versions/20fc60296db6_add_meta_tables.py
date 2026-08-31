"""add meta tables (endpoint registry + field mapping)

Revision ID: 20fc60296db6
Revises: 012
Create Date: 2026-07-29 21:14:11
"""

import sqlalchemy as sa
from alembic import op

revision = "20fc60296db6"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_endpoint",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint_name", sa.String(length=100), nullable=False),
        sa.Column("api_path", sa.String(length=500), nullable=False),
        sa.Column("api_object", sa.String(length=100), nullable=True),
        sa.Column("auth_method", sa.String(length=100), nullable=True),
        sa.Column("raw_table", sa.String(length=100), nullable=False),
        sa.Column("pk_field", sa.String(length=100), nullable=True),
        sa.Column("incremental", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sync_order", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_name"),
    )
    op.create_table(
        "meta_field_mapping",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint_name", sa.String(length=100), nullable=False),
        sa.Column("api_field", sa.String(length=100), nullable=False),
        sa.Column("db_column", sa.String(length=100), nullable=False),
        sa.Column("db_type", sa.String(length=50), nullable=False),
        sa.Column("is_loaded", sa.Boolean(), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["endpoint_name"], ["meta_endpoint.endpoint_name"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_name", "api_field"),
    )


def downgrade() -> None:
    op.drop_table("meta_field_mapping")
    op.drop_table("meta_endpoint")
