from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.telemetry import setup_logging

settings = get_settings()

# Setup logging BEFORE importing endpoints
setup_logging()
logger = structlog.get_logger()

from app.api.deps import get_current_user
from fastapi import Depends

# Import endpoints after logging is configured
from app.api.v1.endpoints import auth, users, apps, api_keys


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Import models to register them with Base
    from app.models import user, app as app_model, api_key
    from app.core.db import engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables initialized")
    logger.info("EagleEye service startup complete")
    yield
    # Shutdown
    logger.info("EagleEye service shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    root_path=settings.API_V1_STR,  # Since it's proxied behind /api/v1/auth etc, might need adjustment, but usually handled by gateway stripping prefix
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    apps.router,
    prefix="/apps",
    tags=["apps"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    api_keys.router, tags=["api-keys"], dependencies=[Depends(get_current_user)]
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.DD_SERVICE,
        "version": settings.VERSION,
    }


@app.get("/")
async def root():
    return {"message": "EagleEye Service Operating"}
