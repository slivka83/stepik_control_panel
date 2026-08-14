"""create mart_* view layer for step/comment/certificate/review analytics

Revision ID: 017
Revises: 016
Create Date: 2026-08-14

Витрины для цифр/графиков/структуры: mart_modules, mart_lessons,
mart_steps, mart_comments, mart_certificates, mart_reviews.

Собираются трансформами из raw-слоя в конце синка (transform_steps →
transform_comments → transform_certificates → transform_reviews). API
читает только их — без прямых запросов к raw_*.

- mart_modules: одна строка на модуль (секцию) курса; модули без юнитов
  сохраняются (структура/воронка).
- mart_lessons: одна строка на урок (юнит); lesson_number — сквозная
  нумерация по курсу.
- mart_steps: одна строка на шаг с путём и метриками; course_id nullable —
  шаги без атрибуции к курсу сохраняются (hardest-steps пути, средняя
  оценка шагов), но не участвуют в структуре/воронке курса.
- mart_comments: одна строка на атрибутированный комментарий (не-
  атрибутируемые пропускаются).
- mart_certificates / mart_reviews: строки сертификатов/отзывов.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def _create_mart_tables() -> None:
    op.create_table(
        "mart_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer(), nullable=False),
        sa.Column("module_number", sa.Integer(), nullable=False),
        sa.Column("module_title", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mart_modules_course_id", "mart_modules", ["course_id"])
    op.create_index("ix_mart_modules_stepik_course_id", "mart_modules", ["stepik_course_id"])

    op.create_table(
        "mart_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("module_number", sa.Integer(), nullable=False),
        sa.Column("module_title", sa.String(), nullable=True),
        sa.Column("lesson_title", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mart_lessons_course_id", "mart_lessons", ["course_id"])
    op.create_index("ix_mart_lessons_stepik_course_id", "mart_lessons", ["stepik_course_id"])
    op.create_index("ix_mart_lessons_lesson_id", "mart_lessons", ["lesson_id"])

    op.create_table(
        "mart_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("stepik_course_id", sa.Integer(), nullable=True),
        sa.Column("step_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=True),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("module_number", sa.Integer(), nullable=True),
        sa.Column("lesson_number", sa.Integer(), nullable=True),
        sa.Column("module_title", sa.String(), nullable=True),
        sa.Column("lesson_title", sa.String(), nullable=True),
        sa.Column("block", sa.String(), nullable=True),
        sa.Column("viewed_by", sa.Integer(), nullable=True),
        sa.Column("passed_by", sa.Integer(), nullable=True),
        sa.Column("correct_ratio", sa.Float(), nullable=True),
        sa.Column("grade", sa.Float(), nullable=True),
        sa.Column("grade_votes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", name="uq_mart_steps_step_id"),
    )
    op.create_index("ix_mart_steps_course_id", "mart_steps", ["course_id"])
    op.create_index("ix_mart_steps_stepik_course_id", "mart_steps", ["stepik_course_id"])

    op.create_table(
        "mart_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("time", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("text", sa.String(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("dislikes", sa.Integer(), nullable=False),
        sa.Column("replies", sa.Integer(), nullable=False),
        sa.Column("is_solution", sa.Boolean(), nullable=False),
        sa.Column("is_unanswered", sa.Boolean(), nullable=False),
        sa.Column("is_disliked", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=True),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("module_number", sa.Integer(), nullable=True),
        sa.Column("lesson_number", sa.Integer(), nullable=True),
        sa.Column("module_title", sa.String(), nullable=True),
        sa.Column("lesson_title", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", name="uq_mart_comments_comment_id"),
    )
    op.create_index("ix_mart_comments_course_id", "mart_comments", ["course_id"])
    op.create_index("ix_mart_comments_stepik_course_id", "mart_comments", ["stepik_course_id"])

    op.create_table(
        "mart_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer(), nullable=False),
        sa.Column("certificate_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mart_certificates_course_id", "mart_certificates", ["course_id"])
    op.create_index("ix_mart_certificates_stepik_course_id", "mart_certificates", ["stepik_course_id"])

    op.create_table(
        "mart_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("stepik_course_id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mart_reviews_course_id", "mart_reviews", ["course_id"])
    op.create_index("ix_mart_reviews_stepik_course_id", "mart_reviews", ["stepik_course_id"])


def _drop_mart_tables() -> None:
    for table, indexes in [
        ("mart_reviews", ["ix_mart_reviews_course_id", "ix_mart_reviews_stepik_course_id"]),
        ("mart_certificates", ["ix_mart_certificates_course_id", "ix_mart_certificates_stepik_course_id"]),
        ("mart_comments", ["ix_mart_comments_course_id", "ix_mart_comments_stepik_course_id"]),
        ("mart_steps", ["ix_mart_steps_course_id", "ix_mart_steps_stepik_course_id"]),
        ("mart_lessons", ["ix_mart_lessons_course_id", "ix_mart_lessons_stepik_course_id", "ix_mart_lessons_lesson_id"]),
        ("mart_modules", ["ix_mart_modules_course_id", "ix_mart_modules_stepik_course_id"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)


def upgrade() -> None:
    _create_mart_tables()


def downgrade() -> None:
    _drop_mart_tables()
