from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry

settings = get_settings()
logger = structlog.get_logger()

from app.api.v1.endpoints import apps, proxy
from app.core.db import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Create tables (for now, simple approach)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables initialized")
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Setup telemetry after app creation but before startup
setup_telemetry(app)

app.include_router(apps.router, prefix="/api/v1/apps", tags=["apps"])
app.include_router(proxy.router, prefix="/api/v1/proxy", tags=["proxy"])


@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "service": settings.OTEL_SERVICE_NAME}

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to Clestiq Shield"}

