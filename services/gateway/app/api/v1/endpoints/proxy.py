from fastapi import APIRouter, Depends, Body, Request, HTTPException, status
from typing import Any, Dict
import httpx
import structlog
from opentelemetry import trace

from app.api import deps
from app.models.application import Application
from app.core.config import get_settings

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

tracer = trace.get_tracer(__name__)


@router.post("/")
async def proxy_request(
    request: Request,
    body: Dict[str, Any] = Body(...),
    current_app: Application = Depends(deps.get_current_app),
):
    """
    Proxy endpoint that accepts any JSON body.
    Authenticated via X-API-Key.
    Routes request to Sentinel (Input Security) for analysis.
    """
    logger.info(
        "Proxy request received",
        app_name=current_app.name,
        app_id=str(current_app.id),
        body_keys=list(body.keys()),
    )

    # Get client info
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    with tracer.start_as_current_span("sentinel_call") as span:
        span.set_attribute("app.name", current_app.name)
        span.set_attribute("app.id", str(current_app.id))

        # Call Sentinel Service
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(
                    "Calling Sentinel service",
                    service_url=settings.SENTINEL_SERVICE_URL,
                )

                response = await client.post(
                    f"{settings.SENTINEL_SERVICE_URL}/chat",
                    json={
                        "input": body,
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
                )

                response.raise_for_status()
                sentinel_result = response.json()

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

    # Check if blocked
    if sentinel_result.get("is_blocked"):
        logger.warning(
            "Request blocked by Sentinel",
            app_name=current_app.name,
            reason=sentinel_result.get("block_reason"),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Request blocked",
                "reason": sentinel_result.get("block_reason"),
            },
        )

    logger.info("Request passed Sentinel check")

    # Return the LLM response from Sentinel (which includes Guardian validation)
    return {
        "response": sentinel_result.get("llm_response"),
        "app": current_app.name,
        "metrics": sentinel_result.get("metrics"),
    }
