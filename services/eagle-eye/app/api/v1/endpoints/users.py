from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.models.user import User
from app.schemas import UserResponse, UserUpdate
from app.api.deps import get_current_user
import structlog

router = APIRouter()
logger = structlog.get_logger()


@router.patch("/", response_model=UserResponse)
async def update_user(
    user_in: UserUpdate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    current_user = result.scalars().first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name

    if user_in.is_active is not None:
        current_user.is_active = user_in.is_active

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/", response_model=UserResponse)
async def get_user(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="User not found")
    return result.scalars().first()


@router.delete("/account-closure", status_code=status.HTTP_204_NO_CONTENT)
async def close_account(
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the user account.
    Fails if the user still owns applications.
    """
    # 1. Check for applications owned by this user
    from app.models.app import Application

    app_result = await db.execute(
        select(Application).where(Application.owner_id == user_id)
    )
    existing_apps = app_result.scalars().all()

    if existing_apps:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete account. You still have active applications. Please delete them first.",
        )

    # 2. Delete user
    result = await db.execute(select(User).where(User.id == user_id))
    current_user = result.scalars().first()
    if current_user:
        await db.delete(current_user)
    await db.commit()
    return None
