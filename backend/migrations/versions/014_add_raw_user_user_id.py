"""add raw_user.user_id (real Stepik user id)

Revision ID: 014
Revises: 013
Create Date: 2026-08-01

raw_user.id — serial-счётчик, а не ID пользователя Stepik: mapping
`id → id` помечен is_loaded=False (serial PK не пишется). Имена
нельзя было связать со студентами. Добавляем user_id (TEXT, как весь
raw-слой) и переводим mapping `id → user_id`.
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("raw_user", sa.Column("user_id", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_raw_user_user_id", "raw_user", ["user_id"])
    op.execute(
        "UPDATE meta_field_mapping "
        "SET db_column = 'user_id', is_loaded = TRUE "
        "WHERE endpoint_name = 'users' AND api_field = 'id'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE meta_field_mapping "
        "SET db_column = 'id', is_loaded = FALSE "
        "WHERE endpoint_name = 'users' AND api_field = 'id'"
    )
    op.drop_constraint("uq_raw_user_user_id", "raw_user")
    op.drop_column("raw_user", "user_id")
