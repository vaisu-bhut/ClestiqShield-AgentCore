from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
import time

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sentinel (Input Security) service startup")
    get_security_metrics()
    yield
    logger.info("Sentinel service shutdown")


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Setup telemetry IMMEDIATELY
setup_telemetry(app)

# Initialize global logger after telemetry
# Initialize global logger after telemetry
logger = structlog.get_logger()

# Import modules AFTER logging is configured
# Import modules AFTER logging is configured
try:
    from app.agents.graph import agent_graph
except Exception as e:
    import traceback

    traceback.print_exc()
    raise

from app.schemas.security import (
    ChatRequest,
    ChatResponse,
    SecurityMetrics,
    GuardianMetrics,
    SentinelConfig,
    GuardianConfig,
)
from app.core.metrics import get_security_metrics, MetricsDataBuilder


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "sentinel"}


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(request: ChatRequest):
    """
    Sentinel Chat Endpoint.
    Orchestrates input security, LLM generation, and output validation.
    """
    logger.info("Received chat request", model=request.model)

    start_time = time.perf_counter()

    # Map Simplified Settings to Internal Configs
    settings = request.settings

    # Sentinel Config (Input)
    sentinel_config = SentinelConfig(
        enable_sanitization=settings.sanitize_input,
        enable_pii_redaction=settings.pii_masking,
        enable_sql_injection_detection=settings.detect_threats,
        enable_xss_protection=settings.detect_threats,
        enable_command_injection_detection=settings.detect_threats,
        enable_toon_conversion=settings.toon_mode,
        enable_llm_forward=settings.enable_llm_forward,
    )

    # Guardian Config (Output)
    guardian_config = GuardianConfig(
        enable_content_filter=settings.content_filter,
        enable_pii_scanner=settings.pii_masking,
        enable_toon_decoder=settings.toon_mode,
        enable_hallucination_detector=settings.hallucination_check,
        enable_citation_verifier=settings.citation_check,
        enable_tone_checker=settings.tone_check,
    )

    input_data = {
        "prompt": request.query,
        "model": request.model,
        "moderation": request.moderation,
        "output_format": request.output_format,
        "max_output_tokens": request.max_output_tokens,
    }

    initial_state = {
        "input": input_data,
        "request": request,
        "client_ip": request.client_ip,
        "user_agent": request.user_agent,
        "security_score": 0.0,
        "is_blocked": False,
        "block_reason": None,
        "sanitized_input": None,
        "pii_detections": [],
        "redacted_input": None,
        "detected_threats": [],
        "llm_response": None,
        "metrics_data": None,
        # INTERNAL CONFIGS
        "sentinel_config": sentinel_config,
        "guardian_config": guardian_config,
    }

    try:
        result = await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Agent graph execution failed: {e}")
        raise

    processing_time_ms = (time.perf_counter() - start_time) * 1000

    if result.get("is_blocked"):
        logger.warning("Request blocked", reason=result.get("block_reason"))
    else:
        logger.info(
            "Request processed",
            model=request.model,
            tokens_saved=result.get("token_savings", 0),
            processing_time_ms=round(processing_time_ms, 2),
        )

    # Construct Guardian Metrics
    guardian_keys = [
        "hallucination_detected",
        "citations_verified",
        "tone_compliant",
        "disclaimer_injected",
        "false_refusal_detected",
        "toxicity_score",
    ]

    # Only include metrics that are actually present (not None)
    present_metrics = {k: result[k] for k in guardian_keys if result.get(k) is not None}

    guardian_metrics = None
    if present_metrics:
        guardian_metrics = GuardianMetrics(**present_metrics)

    metrics_obj = SecurityMetrics(
        security_score=result.get("security_score", 0.0),
        tokens_saved=result.get("token_savings", 0),
        llm_tokens=result.get("llm_tokens_used"),
        model_used=result.get("model_used"),
        threats_detected=len(result.get("detected_threats", [])),
        pii_redacted=len(result.get("pii_detections", [])),
        processing_time_ms=round(processing_time_ms, 2),
        guardian_metrics=guardian_metrics,
    )

    return ChatResponse(
        is_blocked=result.get("is_blocked", False),
        block_reason=result.get("block_reason"),
        llm_response=result.get("llm_response"),
        metrics=metrics_obj,
    )
