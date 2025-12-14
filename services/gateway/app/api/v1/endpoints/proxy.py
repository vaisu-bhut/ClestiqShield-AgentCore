from fastapi import APIRouter, Depends, Request, HTTPException, status, Response
import time
from typing import Optional
import httpx
import structlog
from opentelemetry import trace

from app.api import deps
from app.models.application import Application
from app.core.config import get_settings
from app.schemas.gateway import (
    GatewayRequest,
    GatewayResponse,
    ResponseMetrics,
    TokenUsage,
)

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

tracer = trace.get_tracer(__name__)


@router.post("/", response_model=GatewayResponse)
async def proxy_request(
    request: Request,
    body: GatewayRequest,
    current_app: Application = Depends(deps.get_current_app),
    response: Response = None,  # Inject Response to set headers
):
    """
    Proxy endpoint that accepts structured gateway requests.
    Authenticated via X-API-Key.
    Routes request to Sentinel (Input Security) for analysis.

    Request Body:
        - query: User query/prompt to process
        - model: LLM model to use (default: gemini-2.0-flash)
        - moderation: Content moderation level (strict, moderate, relaxed, raw)
        - output_format: Output format (json or toon)
        - guardrails: Optional guardrails configuration

    Response:
        - response: LLM response content
        - app: Application name
        - metrics: Detailed processing metrics including token usage

    Headers:
        - X-Security-Decision: Explanation of security decision (passed/blocked)
        - X-Security-Score: Threat score (0.0-1.0)
    """
    start_time = time.perf_counter()

    logger.info(
        "Proxy request received",
        app_name=current_app.name,
        app_id=str(current_app.id),
        model=body.model,
        moderation=body.moderation,
    )

    # Get client info
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Build input dict for Sentinel (maintains compatibility)
    sentinel_input = {
        "prompt": body.query,
        "model": body.model,
        "moderation": body.moderation,
        "output_format": body.output_format,
    }

    # Add guardrails config if provided
    if body.guardrails:
        sentinel_input["guardrails"] = body.guardrails.model_dump()

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
                    json={
                        "input": sentinel_input,
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
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

    # Build response metrics
    response_metrics = ResponseMetrics(
        security_score=security_score,
        tokens_saved=sentinel_metrics.get("tokens_saved", 0),
        token_usage=token_usage,
        model_used=sentinel_metrics.get("model_used"),
        threats_detected=sentinel_metrics.get("threats_detected", 0),
        pii_redacted=sentinel_metrics.get("pii_redacted", 0),
        processing_time_ms=round(processing_time_ms, 2),
        # NEW: Guardian validation results
        hallucination_detected=sentinel_metrics.get("hallucination_detected"),
        citations_verified=sentinel_metrics.get("citations_verified"),
        tone_compliant=sentinel_metrics.get("tone_compliant"),
        disclaimer_injected=sentinel_metrics.get("disclaimer_injected"),
        false_refusal_detected=sentinel_metrics.get("false_refusal_detected"),
        toxicity_score=sentinel_metrics.get("toxicity_score"),
    )

    # Return the enhanced response
    return GatewayResponse(
        response=sentinel_result.get("llm_response"),
        app=current_app.name,
        metrics=response_metrics,
    )
