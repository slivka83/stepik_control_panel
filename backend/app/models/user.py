import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stepik_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    access_level: Mapped[str | None] = mapped_column(String, default="Owner")
    financial_inn: Mapped[str | None] = mapped_column(String)
    financial_bik: Mapped[str | None] = mapped_column(String)
    taxation_system: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    courses: Mapped[list["Course"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_stepik_id", "stepik_id"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} stepik_id={self.stepik_id}>"
