"""raw tables schema fixes: missing columns + raw_sync_state

Revision ID: 011
Revises: 010
Create Date: 2026-07-31

- raw_course: cover_url, instructor_ids, intro_text (mapping rows ссылались
  на несуществующие колонки — transform/sync_raw молча теряли данные)
- raw_step: block_video_json, block_is_deprecated, block_type
- raw_sync_state: таблица состояния инкрементального sync (использовалась
  в raw_sync.py, но отсутствовала в PostgreSQL)
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("raw_course", sa.Column("cover_url", sa.Text(), nullable=True))
    op.add_column("raw_course", sa.Column("instructor_ids", sa.Text(), nullable=True))
    op.add_column("raw_course", sa.Column("intro_text", sa.Text(), nullable=True))
    op.add_column("raw_lesson", sa.Column("cover_url", sa.Text(), nullable=True))
    op.add_column("raw_step", sa.Column("block_video_json", sa.Text(), nullable=True))
    op.add_column("raw_step", sa.Column("block_is_deprecated", sa.Text(), nullable=True))
    op.add_column("raw_step", sa.Column("block_type", sa.Text(), nullable=True))
    op.create_table(
        "raw_sync_state",
        sa.Column("endpoint_name", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("endpoint_name", "key"),
    )


def downgrade() -> None:
    op.drop_table("raw_sync_state")
    op.drop_column("raw_step", "block_type")
    op.drop_column("raw_step", "block_is_deprecated")
    op.drop_column("raw_step", "block_video_json")
    op.drop_column("raw_lesson", "cover_url")
    op.drop_column("raw_course", "intro_text")
    op.drop_column("raw_course", "instructor_ids")
    op.drop_column("raw_course", "cover_url")
