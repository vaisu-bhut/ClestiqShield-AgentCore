from fastapi import APIRouter, Depends, Request, HTTPException, status, Response
import time
from typing import Optional
import httpx
import structlog
from opentelemetry import trace

from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.core.config import get_settings
from app.models.api_key import ApiKey
from app.schemas.gateway import (
    GatewayRequest,
    GatewayResponse,
    ResponseMetrics,
    TokenUsage,
)
from app.core.telemetry import telemetry

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

tracer = trace.get_tracer(__name__)


@router.post("/", response_model=GatewayResponse, response_model_exclude_none=True)
async def chat_request(
    request: Request,
    body: GatewayRequest,
    api_key: ApiKey = Depends(deps.get_api_key),
    db: AsyncSession = Depends(deps.get_db),
    response: Response = None,  # Inject Response to set headers
):
    """
    Chat endpoint that accepts structured gateway requests.
    Authenticated via X-API-Key.
    Routes request to Sentinel (Input Security) for analysis.

    Request Body:
        - query: User query/prompt to process
        - model: LLM model to use (default: gemini-3-flash-preview)
        - moderation: Content moderation level (strict, moderate, relaxed, raw)
        - output_format: Output format (json or toon)
        - settings: Security settings object

    Response:
        - response: LLM response content
        - app: Application name
        - metrics: Detailed processing metrics including token usage

    Headers:
        - X-Security-Decision: Explanation of security decision (passed/blocked)
        - X-Security-Score: Threat score (0.0-1.0)
    """
    start_time = time.perf_counter()
    current_app = api_key.application

    logger.info(
        "Chat request received",
        app_name=current_app.name,
        app_id=str(current_app.id),
        model=body.model,
        moderation=body.moderation,
    )

    # Get client info
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Build input body for Sentinel (matching ChatRequest schema)
    sentinel_input = {
        "query": body.query,
        "system_prompt": body.system_prompt,
        "model": body.model,
        "moderation": body.moderation,
        "output_format": body.output_format,
        "max_output_tokens": body.max_output_tokens,
        "settings": body.settings.model_dump(),
        "client_ip": client_ip,
        "user_agent": user_agent,
    }

    with tracer.start_as_current_span("sentinel_call") as span:
        span.set_attribute("app.name", current_app.name)
        span.set_attribute("app.id", str(current_app.id))
        span.set_attribute("llm.model", body.model)

        # Call Sentinel Service
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(
                    "Calling Sentinel service",
                    service_url=settings.SENTINEL_SERVICE_URL,
                )

                sentinel_response = await client.post(
                    f"{settings.SENTINEL_SERVICE_URL}/chat",
                    json=sentinel_input,
                )

                sentinel_response.raise_for_status()
                sentinel_result = sentinel_response.json()

                logger.info(
                    "Sentinel analysis completed",
                    is_blocked=sentinel_result.get("is_blocked"),
                )

        except httpx.HTTPError as e:
            logger.error("Failed to call Sentinel service", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sentinel service unavailable",
            )
        except Exception as e:
            logger.error(
                "Unexpected error calling Sentinel service", error=str(e), exc_info=True
            )
            # Log the actual error for debugging
            logger.error(f"Error details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {str(e)}",
            )

    # Calculate processing time
    processing_time_ms = (time.perf_counter() - start_time) * 1000

    # Extract security decision info
    is_blocked = sentinel_result.get("is_blocked", False)
    block_reason = sentinel_result.get("block_reason", "")
    sentinel_metrics = sentinel_result.get("metrics") or {}
    security_score = sentinel_metrics.get("security_score", 0.0)

    # Set explainability headers
    security_headers = {
        "X-Security-Score": f"{security_score:.3f}",
        "X-Security-Decision": f"blocked: {block_reason}" if is_blocked else "passed",
    }

    if response:
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value

    # Check if blocked
    if is_blocked:
        # Record blocked metric
        telemetry.increment(
            "clestiq.gateway.requests",
            tags=[
                f"app:{current_app.name}",
                f"model:{body.model}",
                "status:blocked",
                f"reason:{block_reason}",
            ],
        )

        logger.warning(
            "Request blocked by Sentinel",
            app_name=current_app.name,
            reason=block_reason,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Request blocked",
                "reason": block_reason,
            },
            headers=security_headers,
        )

    # Record success metric
    telemetry.increment(
        "clestiq.gateway.requests",
        tags=[f"app:{current_app.name}", f"model:{body.model}", "status:passed"],
    )

    logger.info("Request passed Sentinel check")

    # Build token usage if available
    token_usage: Optional[TokenUsage] = None
    llm_tokens = sentinel_metrics.get("llm_tokens")
    if llm_tokens and isinstance(llm_tokens, dict):
        token_usage = TokenUsage(
            input_tokens=llm_tokens.get("input", 0),
            output_tokens=llm_tokens.get("output", 0),
            total_tokens=llm_tokens.get("total", 0),
        )

    # Extract guardian metrics
    guardian_metrics = sentinel_metrics.get("guardian_metrics") or {}

    # Build response metrics
    response_metrics = ResponseMetrics(
        security_score=security_score,
        tokens_saved=sentinel_metrics.get("tokens_saved", 0),
        token_usage=token_usage,
        model_used=sentinel_metrics.get("model_used"),
        threats_detected=sentinel_metrics.get("threats_detected", 0),
        pii_redacted=sentinel_metrics.get("pii_redacted", 0),
        processing_time_ms=round(processing_time_ms, 2),
        # Guardian validation results
        hallucination_detected=guardian_metrics.get("hallucination_detected"),
        citations_verified=guardian_metrics.get("citations_verified"),
        tone_compliant=guardian_metrics.get("tone_compliant"),
        disclaimer_injected=guardian_metrics.get("disclaimer_injected"),
        false_refusal_detected=guardian_metrics.get("false_refusal_detected"),
        toxicity_score=guardian_metrics.get("toxicity_score"),
    )

    # Update Metrics in DB
    from sqlalchemy import func

    api_key.last_used_at = func.now()
    api_key.request_count += 1

    # Update usage_data JSON
    # Structure: {"model_name": {"input_tokens": 0, "output_tokens": 0}}
    current_usage = dict(api_key.usage_data) if api_key.usage_data else {}

    # Extract usage from metrics
    model_used = response_metrics.model_used or body.model
    input_tokens = 0
    output_tokens = 0

    if response_metrics.token_usage:
        input_tokens = response_metrics.token_usage.input_tokens
        output_tokens = response_metrics.token_usage.output_tokens

    if model_used not in current_usage:
        current_usage[model_used] = {"input_tokens": 0, "output_tokens": 0}

    current_usage[model_used]["input_tokens"] += input_tokens
    current_usage[model_used]["output_tokens"] += output_tokens

    # Force update
    api_key.usage_data = current_usage

    await db.commit()

    # --- DATADOG METRICS EXPORT ---
    # 1. Processing Time
    telemetry.histogram(
        "clestiq.gateway.latency",
        processing_time_ms,
        tags=[f"app:{current_app.name}", f"model:{model_used}"],
    )

    # 2. Security Score
    telemetry.gauge(
        "clestiq.gateway.security_score",
        security_score,
        tags=[f"app:{current_app.name}"],
    )

    # 3. Token Usage
    if response_metrics.token_usage:
        telemetry.increment(
            "clestiq.gateway.tokens",
            response_metrics.token_usage.input_tokens,
            tags=[f"app:{current_app.name}", f"model:{model_used}", "type:input"],
        )
        telemetry.increment(
            "clestiq.gateway.tokens",
            response_metrics.token_usage.output_tokens,
            tags=[f"app:{current_app.name}", f"model:{model_used}", "type:output"],
        )
        telemetry.increment(
            "clestiq.gateway.tokens",
            response_metrics.token_usage.total_tokens,
            tags=[f"app:{current_app.name}", f"model:{model_used}", "type:total"],
        )

    # 4. Tokens Saved (Efficiency)
    if response_metrics.tokens_saved > 0:
        telemetry.increment(
            "clestiq.gateway.tokens_saved",
            response_metrics.tokens_saved,
            tags=[f"app:{current_app.name}", f"model:{model_used}"],
        )

    # 5. Guardian Metrics (Reliability & Brand Safety)
    if response_metrics.hallucination_detected:
        telemetry.increment(
            "clestiq.guardian.hallucination",
            tags=[f"app:{current_app.name}", f"model:{model_used}"],
        )

    if response_metrics.threats_detected > 0:
        telemetry.increment(
            "clestiq.gateway.threats",
            response_metrics.threats_detected,
            tags=[f"app:{current_app.name}", f"model:{model_used}"],
        )

    if response_metrics.toxicity_score is not None:
        telemetry.gauge(
            "clestiq.guardian.toxicity",
            response_metrics.toxicity_score,
            tags=[f"app:{current_app.name}"],
        )

    if response_metrics.pii_redacted > 0:
        telemetry.increment(
            "clestiq.gateway.pii_redacted",
            response_metrics.pii_redacted,
            tags=[f"app:{current_app.name}"],
        )

    # Return the enhanced response
    return GatewayResponse(
        response=sentinel_result.get("llm_response"),
        app=current_app.name,
        metrics=response_metrics,
    )
