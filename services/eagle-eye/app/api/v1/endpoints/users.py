from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.models.user import User
from app.schemas import UserResponse, UserUpdate
import structlog
from typing import List

router = APIRouter()
logger = structlog.get_logger()

# Dependencies to get current user would go here (verifying Firebase Token)
# For now, assuming endpoints are protected by Gateway or unimplemented middleware
# We will add a placeholder for current_user dependency


async def get_current_user_placeholder(db: AsyncSession = Depends(get_db)):
    # Placeholder: In real implementation, parse Bearer token -> verify firebase -> get DB user
    # For initial skeleton, returning first user or error
    # This needs proper implementation for real security
    return None


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Further CRUD can be added here
