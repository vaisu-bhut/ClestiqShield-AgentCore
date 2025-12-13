from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.db import Base


class Feedback(Base):
    """Security feedback for false positive reporting and model improvement."""

    __tablename__ = "security_feedback"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Security Event Details
    prompt = Column(Text, nullable=True, comment="Sanitized user prompt (NO PII)")
    response = Column(
        Text, nullable=True, comment="LLM response that was blocked/flagged"
    )
    block_reason = Column(
        String(255),
        nullable=True,
        comment="Reason for blocking (e.g., 'sql_injection')",
    )

    # User Feedback
    user_comment = Column(
        Text,
        nullable=True,
        comment="User's explanation of why this is a false positive",
    )

    # Metadata
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Feedback(id={self.id}, block_reason='{self.block_reason}', created_at={self.created_at})>"
