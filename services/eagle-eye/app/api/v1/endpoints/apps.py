from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.models.app import Application
from app.schemas import ApplicationCreate, ApplicationResponse, ApplicationUpdate
import structlog
from typing import List
from app.api.deps import get_current_user
from app.core.telemetry import telemetry

router = APIRouter()
logger = structlog.get_logger()


@router.post("/", response_model=ApplicationResponse)
async def create_app(
    app_in: ApplicationCreate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # TODO: Link to actual current user
    # For now, create unlinked or link to a test user if exists

    new_app = Application(
        name=app_in.name, description=app_in.description, owner_id=user_id
    )
    db.add(new_app)
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Error creating app: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application with this name already exists",
        )
    await db.refresh(new_app)
    logger.info("Application created", app_id=str(new_app.id))
    telemetry.increment("clestiq.eagleeye.apps.created")
    return new_app


@router.get("/", response_model=List[ApplicationResponse])
async def list_apps(
    skip: int = 0,
    limit: int = 100,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Application)
        .where(Application.owner_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_app(
    app_id: str,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return app


@router.patch("/{app_id}", response_model=ApplicationResponse)
async def update_app(
    app_id: str,
    app_in: ApplicationUpdate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    if app_in.name is not None:
        app.name = app_in.name
    if app_in.description is not None:
        app.description = app_in.description

    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/{app_id}")
async def delete_app(
    app_id: str,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    await db.delete(app)
    await db.commit()
    telemetry.increment("clestiq.eagleeye.apps.deleted")
    return {"message": "Application deleted"}
