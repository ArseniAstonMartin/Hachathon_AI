import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr, as_declarative

@as_declarative()
class Base:
    id: UUID
    __name__: str

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
