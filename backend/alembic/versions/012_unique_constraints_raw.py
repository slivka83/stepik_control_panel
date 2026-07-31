"""unique constraints for upserted raw tables

Revision ID: 012
Revises: 011
Create Date: 2026-07-31

_incremental_upsert_raw_table генерирует ON CONFLICT (submission_id/attempt_id/
comment_id), но в PostgreSQL не было unique-индексов — sync падал с
"there is no unique or exclusion constraint matching the ON CONFLICT
specification" на этапе submissions.
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_raw_submission_submission_id", "raw_submission", ["submission_id"]
    )
    op.create_unique_constraint(
        "uq_raw_attempt_attempt_id", "raw_attempt", ["attempt_id"]
    )
    op.create_unique_constraint(
        "uq_raw_comment_comment_id", "raw_comment", ["comment_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_raw_comment_comment_id", "raw_comment")
    op.drop_constraint("uq_raw_attempt_attempt_id", "raw_attempt")
    op.drop_constraint("uq_raw_submission_submission_id", "raw_submission")
