from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.models.base import Base


class MetaFieldMapping(Base):
    __tablename__ = "meta_field_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_name = Column(String(100), ForeignKey("meta_endpoint.endpoint_name"), nullable=False)
    api_field = Column(String(100), nullable=False)
    db_column = Column(String(100), nullable=False)
    db_type = Column(String(50), nullable=False)
    is_loaded = Column(Boolean, default=True, nullable=False)
    skip_reason = Column(Text)
    description = Column(Text)

    __table_args__ = (UniqueConstraint("endpoint_name", "api_field"),)
