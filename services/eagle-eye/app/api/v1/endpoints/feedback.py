from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.db import get_db
from app.models.feedback import Feedback
import structlog
from typing import Optional

router = APIRouter()
logger = structlog.get_logger()


class FeedbackCreate(BaseModel):
    """Schema for creating security feedback."""

    prompt: Optional[str] = None
    response: Optional[str] = None
    block_reason: Optional[str] = None
    user_comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""

    id: int
    block_reason: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback_in: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit false positive feedback for security decisions.

    This endpoint allows users to report when the security agent incorrectly
    blocked a legitimate request. Data is stored for analysis and model improvement.

    **IMPORTANT**: Do NOT submit PII in the prompt field. The prompt should already
    be sanitized/pseudonymized.
    """
    new_feedback = Feedback(
        prompt=feedback_in.prompt,
        response=feedback_in.response,
        block_reason=feedback_in.block_reason,
        user_comment=feedback_in.user_comment,
    )

    db.add(new_feedback)
    await db.commit()
    await db.refresh(new_feedback)

    logger.info(
        "Feedback submitted",
        feedback_id=new_feedback.id,
        block_reason=feedback_in.block_reason,
    )

    return FeedbackResponse(
        id=new_feedback.id,
        block_reason=new_feedback.block_reason,
        created_at=new_feedback.created_at.isoformat()
        if new_feedback.created_at
        else "",
    )
