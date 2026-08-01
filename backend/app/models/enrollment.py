import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_joined: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cohort_status: Mapped[str | None] = mapped_column(String, default="Active")
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    course: Mapped["Course"] = relationship(back_populates="enrollments")

    __table_args__ = (
        Index("ix_student_enrollments_course_id", "course_id"),
        Index("ix_student_enrollments_student_id", "student_id"),
        Index("ix_student_enrollments_last_viewed", "last_viewed_at"),
        Index("ix_student_enrollments_course_student", "course_id", "student_id"),
        UniqueConstraint("course_id", "student_id", name="uq_enrollment"),
    )

    def __repr__(self) -> str:
        return f"<StudentEnrollment id={self.id} course_id={self.course_id} student_id={self.student_id}>"
