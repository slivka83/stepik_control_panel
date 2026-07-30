from sqlalchemy import Column, String, Boolean, Text, Integer
from app.models.base import Base


class MetaEndpoint(Base):
    __tablename__ = "meta_endpoint"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_name = Column(String(100), unique=True, nullable=False)
    api_path = Column(String(255), nullable=False)
    api_object = Column(String(100))
    auth_method = Column(String(50), default="user_token")
    raw_table = Column(String(100), nullable=False)
    pk_field = Column(String(100))
    incremental = Column(String(50))
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    sync_order = Column(Integer)
