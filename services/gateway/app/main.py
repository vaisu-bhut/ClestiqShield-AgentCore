from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings


settings = get_settings()
from app.core.db import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Tables are managed by EagleEye service to avoid race conditions
    # We import models to ensuring mapping, but do not create tables here.
    from app.models.application import Application
    from app.models.api_key import ApiKey

    # Use local logger or ensured global logger
    logger.info("Database tables initialized (skipped in Gateway)")
    logger.info("Gateway service startup complete")
    yield
    # Shutdown
    logger.info("Gateway service shutdown")


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize global logger AFTER telemetry setup
logger = structlog.get_logger()

# Import endpoints AFTER logging is configured
from app.api.v1.endpoints import chat, router_eagleeye


app.include_router(chat.router, prefix="/chat", tags=["chat"])

# Dynamic Proxy for EagleEye (Auth, Users, Apps, Keys)
# We want to forward /api/v1/auth, /api/v1/users, /api/v1/apps (override?)
# Actually, the existing /api/v1/apps in gateway is minimal. The user asked for "routes can be sign in/up, user management, app management".
# So implementation in EagleEye covers /apps.
# We should probably REMOVE the old apps endpoint or comment it out if EagleEye takes over.
# For now, let's mount the proxy to handle specific prefixes.

# Proxy specific paths to EagleEye
app.include_router(router_eagleeye.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(router_eagleeye.router, prefix="/api/v1/users", tags=["users"])
# If EagleEye manages apps now, we should proxy /apps too.
# BEWARE: The existing apps router in Gateway might conflict.
# The user wants "this new pod... communicates directly and only with gateway... routes can be... app management"
# So I should disable the local apps router and proxy to EagleEye.
# app.include_router(apps.router, prefix="/api/v1/apps", tags=["apps"]) # DISABLED
app.include_router(router_eagleeye.router, prefix="/api/v1/apps", tags=["apps"])
app.include_router(router_eagleeye.router, prefix="/api/v1/feedback", tags=["feedback"])


@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {
        "status": "ok",
        "service": settings.DD_SERVICE,
        "version": settings.VERSION,
    }


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to Clestiq Shield Gateway", "version": settings.VERSION}
