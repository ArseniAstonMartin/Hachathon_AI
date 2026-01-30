from sqlalchemy import Column, Integer, String, Boolean
from src.auth_manager.models.base import Base


class Users(Base):
    __tablename__ = "worker_base"

    worker_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String(128), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_localadmin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, server_default="true")
    first_name = Column(String, nullable=False)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=False)