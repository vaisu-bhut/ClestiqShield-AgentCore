from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.core.security import generate_api_key, hash_api_key, mask_api_key
from app.models.api_key import ApiKey
from app.models.app import Application
from app.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeySecret
import structlog
from typing import List

router = APIRouter()
logger = structlog.get_logger()


from app.models.user import User
from app.api.deps import get_current_user


@router.post("/apps/{app_id}/keys", response_model=ApiKeySecret)
async def create_api_key(
    app_id: str,
    key_in: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify app exists
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Generate Key
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    key_prefix = plain_key[:4]

    new_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_in.name,
        application_id=app.id,
    )

    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    # Return Schema with SECRET plain key
    return ApiKeySecret(
        id=new_key.id,
        key_prefix=new_key.key_prefix,
        name=new_key.name,
        created_at=new_key.created_at,
        last_used_at=new_key.last_used_at,
        is_active=new_key.is_active,
        api_key=plain_key,  # IMPORTANT: Shown only once
    )


@router.get("/apps/{app_id}/keys", response_model=List[ApiKeyResponse])
async def list_api_keys(app_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).where(ApiKey.application_id == app_id))
    return result.scalars().all()


@router.delete("/apps/{app_id}/keys/{key_id}")
async def revoke_api_key(app_id: str, key_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.application_id == app_id)
    )
    key = result.scalars().first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")

    await db.delete(key)  # Or set is_active = False for soft delete
    await db.commit()
    return {"message": "API Key revoked"}
