"""add submissions step tracking and step_sync_state

Revision ID: 006
Revises: 005
Create Date: 2026-07-25
"""

import sqlalchemy as sa

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("stepik_submission_id", sa.Integer(), nullable=True))
    op.add_column("submissions", sa.Column("stepik_step_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_stepik_submission_id", "submissions", ["stepik_submission_id"])
    op.create_index("ix_submissions_stepik_step_id", "submissions", ["stepik_step_id"])

    op.create_table(
        "step_sync_state",
        sa.Column("step_id", sa.Integer(), primary_key=True),
        sa.Column("last_page", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("step_sync_state")
    op.drop_index("ix_submissions_stepik_step_id", "submissions")
    op.drop_constraint("uq_stepik_submission_id", "submissions", type_="unique")
    op.drop_column("submissions", "stepik_step_id")
    op.drop_column("submissions", "stepik_submission_id")
