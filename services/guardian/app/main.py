from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Guardian (Output Validation) service startup")
    get_guardian_metrics()
    yield
    logger.info("Guardian service shutdown")


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Setup telemetry IMMEDIATELY
setup_telemetry(app)

# Initialize global logger after telemetry
logger = structlog.get_logger()

# Import modules AFTER logging is configured to ensure they use the correct logger factory
from app.agents.graph import guardian_graph
from app.schemas.validation import ValidateRequest, ValidateResponse
from app.core.metrics import get_guardian_metrics


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
        "guardrails": request.guardrails,
        "original_query": request.original_query,
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

    # DEBUG: Log what we got back
    logger.info(
        "Graph execution complete",
        hallucination_detected=result.get("hallucination_detected"),
        citations_verified=result.get("citations_verified"),
        tone_compliant=result.get("tone_compliant"),
        disclaimer_injected=result.get("disclaimer_injected"),
        false_refusal_detected=result.get("false_refusal_detected"),
        toxicity_score=result.get("toxicity_score"),
    )

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
        # NEW: Advanced validation results
        hallucination_detected=result.get("hallucination_detected"),
        hallucination_details=result.get("hallucination_details"),
        citations_verified=result.get("citations_verified"),
        fake_citations=result.get("fake_citations"),
        tone_compliant=result.get("tone_compliant"),
        tone_violation_reason=result.get("tone_violation_reason"),
        disclaimer_injected=result.get("disclaimer_injected"),
        disclaimer_text=result.get("disclaimer_text"),
        false_refusal_detected=result.get("false_refusal_detected"),
        toxicity_score=result.get("toxicity_score"),
        toxicity_details=result.get("toxicity_details"),
        metrics={
            "moderation_mode": request.moderation_mode,
            "warnings_count": len(result.get("content_warnings", [])),
            "pii_leaks_count": len(result.get("output_pii_leaks", [])),
        },
    )
