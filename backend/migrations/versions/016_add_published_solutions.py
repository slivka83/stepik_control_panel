"""add published_solutions to student_marts

Revision ID: 016
Revises: 015
Create Date: 2026-08-06

Колонка «Опубликованные решения» в витрине студентов: число комментариев
студента в тредах решений (thread содержит «solution»). Считается
transform_students из raw_comment, по аналогии с comments_count.
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_marts",
        sa.Column("published_solutions", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("student_marts", "published_solutions")
