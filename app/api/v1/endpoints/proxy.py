from fastapi import APIRouter, Depends, Body, Request
from typing import Any, Dict
from app.api import deps
from app.models.application import Application
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.post("/")
async def proxy_request(
    request: Request,
    body: Dict[str, Any] = Body(...),
    current_app: Application = Depends(deps.get_current_app)
):
    """
    Proxy endpoint that accepts any JSON body.
    Authenticated via X-API-Key.
    """
    logger.info(
        "Proxy request received", 
        app_name=current_app.name, 
        app_id=str(current_app.id),
        body_keys=list(body.keys())
    )
    
    # In the future, this is where the Agent Orchestrator will be called.
    # For now, we just echo back success.
    
    return {
        "message": "Request received and authenticated",
        "app": current_app.name,
        "received_body": body
    }
