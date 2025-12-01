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
    current_app: Application = Depends(deps.get_current_app)
):
    """
    Proxy endpoint that accepts any JSON body.
    Authenticated via X-API-Key.
    Routes request to Security Agent Service for analysis.
    """
    logger.info(
        "Proxy request received", 
        app_name=current_app.name, 
        app_id=str(current_app.id),
        body_keys=list(body.keys())
    )
    
    # Get client info
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    with tracer.start_as_current_span("security_agent_call") as span:
        span.set_attribute("app.name", current_app.name)
        span.set_attribute("app.id", str(current_app.id))
        
        # Call Security Agent Service
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(
                    "Calling security agent service",
                    service_url=settings.SECURITY_SERVICE_URL
                )
                
                response = await client.post(
                    f"{settings.SECURITY_SERVICE_URL}/analyze",
                    json={
                        "input": body,
                        "client_ip": client_ip,
                        "user_agent": user_agent
                    }
                )
                
                response.raise_for_status()
                security_result = response.json()
                
                logger.info(
                    "Security analysis completed",
                    is_blocked=security_result.get("is_blocked"),
                    security_score=security_result.get("security_score")
                )
                
        except httpx.HTTPError as e:
            logger.error(
                "Failed to call security agent service",
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security service unavailable"
            )
        except Exception as e:
            logger.error(
                "Unexpected error calling security service",
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
    
    # Check if blocked
    if security_result.get("is_blocked"):
        logger.warning(
            "Request blocked by security agent",
            app_name=current_app.name,
            reason=security_result.get("block_reason"),
            score=security_result.get("security_score")
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Request blocked",
                "reason": security_result.get("block_reason"),
                "security_score": security_result.get("security_score")
            }
        )
    
    logger.info("Request passed security check", score=security_result.get("security_score"))
    
    # For now, just return success (later will continue to other agents/LLM)
    return {
        "message": "Request received and passed security check",
        "app": current_app.name,
        "security_score": security_result.get("security_score"),
        "received_body": body
    }
