"""reconcile migration chain with models (fix broken fresh installs)

Revision ID: 019
Revises: 018
Create Date: 2026-08-28

Regression: `alembic upgrade head` на пустой базе строила схему, несовпадающую
с моделями — приложение не могло работать без ручного create_all:
- financial_snapshots вообще не создавалась ни одной миграцией (005 ссылался
  на таблицу внутри try/except, который молча глотал ошибку);
- submissions: отсутствовали score/language/attempt_id/eta; оставались
  зомби-колонки step_id/student_id и не было уникального констрейнта
  uq_stepik_submission_id;
- student_enrollments: отсутствовала date_joined;
- step_sync_state: зомби-таблица из 006, которую ни один код не использует.

Все операции идемпотентны (IF [NOT] EXISTS / DO-block) — миграция безопасна
на живой базе, где схема уже совпадает с моделями.

Проверяется тестом TestMigrationsBuildModelSchema (test_architecture.py).
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # financial_snapshots: едиственная витрина финансов — обязана существовать
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_snapshots (
            id UUID NOT NULL PRIMARY KEY,
            data JSONB NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    # submissions: недостающие колонки моделей + уникальность по submission_id
    op.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS language VARCHAR")
    op.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS attempt_id INTEGER")
    op.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS eta INTEGER NOT NULL DEFAULT 0")
    # зомби-колонки из 004 (в моделях их никогда не было)
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS step_id")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS student_id")
    # констрейнт/индекс моделей (ADD CONSTRAINT без IF NOT EXISTS — через индекс)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_stepik_submission_id ON submissions (stepik_submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_stepik_step_id ON submissions (stepik_step_id)")

    # student_enrollments: date_joined (когортный статус «Зомби»)
    op.execute("ALTER TABLE student_enrollments ADD COLUMN IF NOT EXISTS date_joined TIMESTAMP WITH TIME ZONE")

    # зомби-таблица из 006 — не используется ни приложением, ни скриптами
    op.execute("DROP TABLE IF EXISTS step_sync_state")


def downgrade() -> None:
    op.create_table(
        "step_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stepik_step_id", sa.Integer(), nullable=False),
        sa.Column("last_page", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_index("ix_submissions_stepik_step_id", table_name="submissions")
    op.execute("DROP INDEX IF EXISTS uq_stepik_submission_id")
    op.add_column("submissions", sa.Column("student_id", sa.Integer(), nullable=True))
    op.add_column("submissions", sa.Column("step_id", sa.Integer(), nullable=True))
    op.drop_column("submissions", "eta")
    op.drop_column("submissions", "attempt_id")
    op.drop_column("submissions", "language")
    op.drop_column("submissions", "score")
    op.drop_column("student_enrollments", "date_joined")
    op.drop_table("financial_snapshots")
