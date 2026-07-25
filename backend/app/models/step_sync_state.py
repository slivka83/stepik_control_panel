from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StepSyncState(Base):
    __tablename__ = "step_sync_state"

    step_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<StepSyncState step_id={self.step_id} last_page={self.last_page}>"
