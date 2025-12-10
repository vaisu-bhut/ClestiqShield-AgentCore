from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.core.db import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True, nullable=False, unique=True)
    description = Column(String)

    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", backref="applications")
    api_keys = relationship(
        "ApiKey", back_populates="application", cascade="all, delete-orphan"
    )
