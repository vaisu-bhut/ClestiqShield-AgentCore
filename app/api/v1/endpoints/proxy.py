from fastapi import APIRouter, Depends, Body, Request, HTTPException, status
from typing import Any, Dict
from app.api import deps
from app.models.application import Application
from app.agents.graph import agent_graph
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
    Runs the request through the Security Agent workflow.
    """
    logger.info(
        "Proxy request received", 
        app_name=current_app.name, 
        app_id=str(current_app.id),
        body_keys=list(body.keys())
    )
    
    # Initialize agent state
    initial_state = {
        "input": body,
        "security_score": 0.0,
        "is_blocked": False,
        "block_reason": None
    }
    
    # Run through the agent graph
    result = await agent_graph.ainvoke(initial_state)
    
    # Check if blocked
    if result.get("is_blocked"):
        logger.warning(
            "Request blocked by security agent",
            app_name=current_app.name,
            reason=result.get("block_reason"),
            score=result.get("security_score")
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Request blocked",
                "reason": result.get("block_reason"),
                "security_score": result.get("security_score")
            }
        )
    
    logger.info("Request passed security check", score=result.get("security_score"))
    
    # For now, just return success (later will continue to other agents)
    return {
        "message": "Request received and passed security check",
        "app": current_app.name,
        "security_score": result.get("security_score"),
        "received_body": body
    }
