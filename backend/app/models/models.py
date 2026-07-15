import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Boolean, Float, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stepik_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    access_level: Mapped[str | None] = mapped_column(String, default="Owner")
    financial_inn: Mapped[str | None] = mapped_column(String)
    financial_bik: Mapped[str | None] = mapped_column(String)
    taxation_system: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    courses: Mapped[list["Course"]] = relationship(back_populates="user")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    stepik_course_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str | None] = mapped_column(String, default="Draft")
    unit_schedule: Mapped[dict | None] = mapped_column(JSONB, default={})
    content_cache: Mapped[dict | None] = mapped_column(JSONB, default={})
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user: Mapped["User"] = relationship(back_populates="courses")
    enrollments: Mapped[list["StudentEnrollment"]] = relationship(back_populates="course")
    transactions: Mapped[list["FinancialTransaction"]] = relationship(back_populates="course")


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, nullable=False)
    student_email: Mapped[str | None] = mapped_column(String)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cohort_status: Mapped[str | None] = mapped_column(String, default="Active")
    is_in_wishlist: Mapped[bool] = mapped_column(Boolean, default=False)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    course: Mapped["Course"] = relationship(back_populates="enrollments")


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_refund: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_b2b: Mapped[bool] = mapped_column(Boolean, default=False)
    ltv_cohort: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    course: Mapped["Course"] = relationship(back_populates="transactions")


class CompetitorCourse(Base):
    __tablename__ = "competitor_courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    competitor_course_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    rating: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    students_count: Mapped[int | None] = mapped_column(Integer)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
