from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Integer, JSON
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_prefix = Column(String, nullable=False)
    key_hash = Column(String, index=True, nullable=False)  # Matches EagleEye
    name = Column(String)

    application_id = Column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False
    )

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))

    # Usage Stats
    request_count = Column(Integer, default=0)
    usage_data = Column(JSON, default=dict)

    application = relationship("Application", back_populates="api_keys")
