import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MartModule(Base):
    """Витрина модулей (секций): одна строка на модуль курса.

    Собирается трансформом из raw_section. Модули без юнитов/шагов
    сохраняются (нужны в структуре и воронке курса).
    """

    __tablename__ = "mart_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    stepik_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)
    module_title: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_mart_modules_course_id", "course_id"),
        Index("ix_mart_modules_stepik_course_id", "stepik_course_id"),
    )

    def __repr__(self) -> str:
        return f"<MartModule course={self.stepik_course_id} n={self.module_number}>"


class MartLesson(Base):
    """Витрина уроков: одна строка на урок (юнит) курса.

    lesson_number — сквозная нумерация по курсу (как в структуре).
    Уроки без шагов сохраняются.
    """

    __tablename__ = "mart_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    stepik_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)
    module_title: Mapped[str | None] = mapped_column(String, nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_mart_lessons_course_id", "course_id"),
        Index("ix_mart_lessons_stepik_course_id", "stepik_course_id"),
        Index("ix_mart_lessons_lesson_id", "lesson_id"),
    )

    def __repr__(self) -> str:
        return f"<MartLesson course={self.stepik_course_id} lesson={self.lesson_id}>"


class MartStep(Base):
    """Витрина шагов: одна строка на шаг с путём и метриками.

    course_id nullable — шаги без атрибуции к курсу (нет unit→section→course)
    сохраняются с пустым course_id: они нужны для hardest-steps путей и
    средней оценки шагов (kpi), но не участвуют в структуре/воронке курса.
    """

    __tablename__ = "mart_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True
    )
    stepik_course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module_title: Mapped[str | None] = mapped_column(String, nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String, nullable=True)
    block: Mapped[str | None] = mapped_column(String, nullable=True)
    viewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_mart_steps_course_id", "course_id"),
        Index("ix_mart_steps_stepik_course_id", "stepik_course_id"),
    )

    def __repr__(self) -> str:
        return f"<MartStep step={self.step_id} course={self.stepik_course_id}>"


class MartComment(Base):
    """Витрина комментариев: одна строка на атрибутированный комментарий.

    Только комментарии, чей шаг атрибутирован к курсу (step→course map).
    Лайки/Дизлайки — сумма положительных/отрицательных vote_delta.
    """

    __tablename__ = "mart_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    stepik_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    comment_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    time: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    dislikes: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    is_solution: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unanswered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_disliked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    module_title: Mapped[str | None] = mapped_column(String, nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_mart_comments_course_id", "course_id"),
        Index("ix_mart_comments_stepik_course_id", "stepik_course_id"),
    )

    def __repr__(self) -> str:
        return f"<MartComment comment={self.comment_id} course={self.stepik_course_id}>"


class MartCertificate(Base):
    """Витрина сертификатов: одна строка на сертификат."""

    __tablename__ = "mart_certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    stepik_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    certificate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_mart_certificates_course_id", "course_id"),
        Index("ix_mart_certificates_stepik_course_id", "stepik_course_id"),
    )

    def __repr__(self) -> str:
        return f"<MartCertificate cert={self.certificate_id} course={self.stepik_course_id}>"


class MartReview(Base):
    """Витрина отзывов: одна строка на отзыв на курс."""

    __tablename__ = "mart_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    stepik_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    review_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_mart_reviews_course_id", "course_id"),
        Index("ix_mart_reviews_stepik_course_id", "stepik_course_id"),
    )

    def __repr__(self) -> str:
        return f"<MartReview review={self.review_id} course={self.stepik_course_id}>"
