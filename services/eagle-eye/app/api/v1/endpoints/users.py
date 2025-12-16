from fastapi import APIRouter, Depends, HTTPException, status
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.
    """
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name

    if user_in.is_active is not None:
        current_user.is_active = user_in.is_active

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


@router.delete("/account-closure", status_code=status.HTTP_204_NO_CONTENT)
async def close_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete the user account.
    Fails if the user still owns applications.
    """
    # 1. Check for applications owned by this user
    from app.models.app import Application

    app_result = await db.execute(
        select(Application).where(Application.owner_id == current_user.id)
    )
    existing_apps = app_result.scalars().all()

    if existing_apps:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete account. You still have active applications. Please delete them first.",
        )

    # 2. Delete user
    await db.delete(current_user)
    await db.commit()
    return None
