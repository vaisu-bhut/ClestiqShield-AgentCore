from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry
from app.core.metrics import get_guardian_metrics
from app.schemas.validation import ValidateRequest, ValidateResponse
from app.agents.graph import guardian_graph

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Guardian (Output Validation) service startup")
    get_guardian_metrics()
    yield
    logger.info("Guardian service shutdown")


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

setup_telemetry(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": settings.OTEL_SERVICE_NAME,
        "version": settings.VERSION,
    }


@app.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest):
    """
    Validate and filter LLM response.

    - Content filtering based on moderation mode
    - PII leak detection and redaction
    - TOON to JSON conversion if needed
    """
    logger.info(
        "Validation request received",
        moderation_mode=request.moderation_mode,
        output_format=request.output_format,
    )

    metrics = get_guardian_metrics()
    metrics.record_request(request.moderation_mode)

    initial_state = {
        "llm_response": request.llm_response,
        "moderation_mode": request.moderation_mode,
        "output_format": request.output_format,
        "content_filtered": False,
        "content_warnings": [],
        "content_blocked": False,
        "content_block_reason": None,
        "output_pii_leaks": [],
        "output_redacted": False,
        "was_toon": False,
        "validated_response": None,
        "validation_passed": True,
        "metrics_data": None,
    }

    result = await guardian_graph.ainvoke(initial_state)

    # Determine validation result
    validation_passed = not result.get("content_blocked", False)
    validated_response = result.get("llm_response") if validation_passed else None

    if result.get("content_blocked"):
        logger.warning(
            "Content blocked",
            reason=result.get("content_block_reason"),
        )
    else:
        logger.info(
            "Validation passed",
            pii_redacted=result.get("output_redacted", False),
            was_toon=result.get("was_toon", False),
        )

    return ValidateResponse(
        validated_response=validated_response,
        validation_passed=validation_passed,
        content_blocked=result.get("content_blocked", False),
        content_block_reason=result.get("content_block_reason"),
        content_warnings=result.get("content_warnings"),
        output_pii_leaks=result.get("output_pii_leaks"),
        output_redacted=result.get("output_redacted", False),
        was_toon=result.get("was_toon", False),
        metrics={
            "moderation_mode": request.moderation_mode,
            "warnings_count": len(result.get("content_warnings", [])),
            "pii_leaks_count": len(result.get("output_pii_leaks", [])),
        },
    )
