from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import secrets
from app.core.db import get_db
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationResponse
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.post("/", response_model=ApplicationResponse)
async def create_application(
    app_in: ApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    # Generate a secure random API key
    api_key = secrets.token_urlsafe(32)
    
    new_app = Application(
        name=app_in.name,
        api_key=api_key
    )
    
    db.add(new_app)
    try:
        await db.commit()
        await db.refresh(new_app)
        logger.info("Application created", app_id=str(new_app.id), app_name=new_app.name)
        return new_app
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application with this name already exists"
        )
