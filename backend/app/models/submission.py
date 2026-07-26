import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Float, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stepik_submission_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stepik_step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta: Mapped[int] = mapped_column(Integer, default=0)
    submission_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_author: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    course: Mapped["Course"] = relationship(back_populates="submissions")

    __table_args__ = (
        UniqueConstraint("stepik_submission_id", name="uq_stepik_submission_id"),
        Index("ix_submissions_course_id", "course_id"),
        Index("ix_submissions_stepik_step_id", "stepik_step_id"),
    )

    def __repr__(self) -> str:
        return f"<Submission id={self.id} status={self.status!r}>"
