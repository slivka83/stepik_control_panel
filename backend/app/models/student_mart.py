import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentMart(Base):
    """Витрина студентов: одна строка на студента автора.

    Пересобирается целиком в конце синка из student_enrollments,
    submissions, raw_comment и raw_user.
    """

    __tablename__ = "student_marts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    cohort_status: Mapped[str | None] = mapped_column(String, nullable=True)
    courses_count: Mapped[int] = mapped_column(Integer, default=0)
    certificates: Mapped[int] = mapped_column(Integer, default=0)
    submissions_count: Mapped[int] = mapped_column(Integer, default=0)
    submissions_successful: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("ix_student_marts_student_id", "student_id"),
        Index("ix_student_marts_last_activity", "last_activity"),
    )

    def __repr__(self) -> str:
        return f"<StudentMart student_id={self.student_id} name={self.name!r}>"
