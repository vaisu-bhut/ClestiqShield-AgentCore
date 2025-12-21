from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog

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

from app.schemas.security import ChatRequest, ChatResponse
from app.core.metrics import get_security_metrics


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": settings.DD_SERVICE}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Core endpoint for processing user queries through the security pipeline.

    Flow: Input → Sanitization → PII → Threats → LLM → Guardian → Response

    All metrics automatically sent to Datadog via OTel.
    """
    import time

    import time

    logger.info(
        "Chat request received",
        client_ip=request.client_ip,
        model=request.input.get("model"),
        moderation=request.input.get("moderation"),
    )

    initial_state = {
        "input": request.input,
        "security_score": 0.0,
        "is_blocked": False,
        "block_reason": None,
        "client_ip": request.client_ip,
        "user_agent": request.user_agent,
        "metrics_data": None,
    }

    try:
        result = await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Agent graph execution failed: {e}")
        raise

    if result.get("is_blocked"):
        logger.warning("Request blocked", reason=result.get("block_reason"))
    else:
        logger.info(
            "Request processed",
            model=request.input.get("model", settings.LLM_MODEL_NAME),
            tokens_saved=result.get("token_savings", 0),
        )

    # Extract Guardian validation results
    guardian_validation = result.get("guardian_validation", {})

    return ChatResponse(
        is_blocked=result.get("is_blocked", False),
        block_reason=result.get("block_reason"),
        llm_response=result.get("llm_response"),
        metrics={
            "security_score": result.get("security_score", 0.0),
            "tokens_saved": result.get("token_savings", 0),
            "llm_tokens": result.get("llm_tokens_used"),
            "model_used": result.get("model_used"),
            "threats_detected": len(result.get("detected_threats", [])),
            "pii_redacted": len(result.get("pii_detections", [])),
            # NEW: Guardian validation results
            "hallucination_detected": guardian_validation.get("hallucination_detected"),
            "citations_verified": guardian_validation.get("citations_verified"),
            "tone_compliant": guardian_validation.get("tone_compliant"),
            "disclaimer_injected": guardian_validation.get("disclaimer_injected"),
            "false_refusal_detected": guardian_validation.get("false_refusal_detected"),
            "toxicity_score": guardian_validation.get("toxicity_score"),
        },
    )
