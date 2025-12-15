from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Use HTTP Exporter for Traces (port 4318)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from app.core.config import get_settings
from app.core.telemetry import setup_logging
from app.api.v1.endpoints import auth, users, apps, api_keys, feedback

settings = get_settings()
setup_logging()
logger = structlog.get_logger()


# Setup Telemetry
def setup_telemetry(app: FastAPI):
    if settings.TELEMETRY_ENABLED:
        resource = Resource(attributes={"service.name": settings.OTEL_SERVICE_NAME})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        # HTTP Exporter endpoint usually expects /v1/traces appended or handled by class
        # OTLPSpanExporter (HTTP) defaults to v1/traces if not present?
        # Let's be explicit: endpoint/v1/traces
        endpoint = f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        # Instrument FastAPI
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Import models to register them with Base
    from app.models import user, app as app_model, api_key, feedback as feedback_model
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

setup_telemetry(app)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(apps.router, prefix="/apps", tags=["apps"])
app.include_router(api_keys.router, tags=["api-keys"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.OTEL_SERVICE_NAME,
        "version": settings.VERSION,
    }


@app.get("/")
async def root():
    return {"message": "EagleEye Service Operating"}
