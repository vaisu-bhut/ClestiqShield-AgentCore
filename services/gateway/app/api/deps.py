from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import hashlib
import structlog

from app.core.db import get_db
from app.models.api_key import ApiKey

logger = structlog.get_logger()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: str = Security(api_key_header), db: AsyncSession = Depends(get_db)
) -> ApiKey:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key header",
        )

    # Hash the API key to match stored hash
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()

    # Check against ApiKey table
    result = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.application))
        .filter(ApiKey.key_hash == hashed_key)
    )
    api_key_obj = result.scalars().first()

    if not api_key_obj:
        logger.warning(
            "Authentication failed: Key not found", api_key_prefix=api_key[:4] + "..."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    if not api_key_obj.is_active:
        logger.warning(
            "Authentication failed: Key disabled", api_key_prefix=api_key[:4] + "..."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key blocked by application",
        )

    if not api_key_obj.application:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key (No App)",
        )

    return api_key_obj
