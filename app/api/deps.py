from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.db import get_db
from app.models.application import Application
import structlog

logger = structlog.get_logger()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_app(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> Application:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key header",
        )

    result = await db.execute(select(Application).filter(Application.api_key == api_key))
    app = result.scalars().first()

    if not app:
        logger.warning("Authentication failed", api_key_prefix=api_key[:4] + "...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    
    return app
