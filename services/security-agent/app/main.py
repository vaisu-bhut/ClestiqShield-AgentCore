from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import structlog

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry
from app.schemas.security import SecurityAnalysisRequest, SecurityAnalysisResponse
from app.agents.graph import agent_graph

settings = get_settings()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Security Agent service startup complete")
    yield
    # Shutdown
    logger.info("Security Agent service shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Setup telemetry after app creation
setup_telemetry(app)

@app.post("/analyze", response_model=SecurityAnalysisResponse)
async def analyze_request(request: SecurityAnalysisRequest):
    """
    Analyzes a request for security threats.
    Runs through the complete security agent graph.
    """
    logger.info(
        "Security analysis requested",
        input_keys=list(request.input.keys()),
        client_ip=request.client_ip
    )
    
    # Initialize agent state
    initial_state = {
        "input": request.input,
        "security_score": 0.0,
        "is_blocked": False,
        "block_reason": None,
        "client_ip": request.client_ip,
        "user_agent": request.user_agent
    }
    
    try:
        # Run through the agent graph
        result = await agent_graph.ainvoke(initial_state)
        
        # Log the result
        if result.get("is_blocked"):
            logger.warning(
                "Request blocked by security agent",
                reason=result.get("block_reason"),
                score=result.get("security_score")
            )
        else:
            logger.info(
                "Request passed security check",
                score=result.get("security_score")
            )
        
        # Return the analysis result
        return SecurityAnalysisResponse(
            security_score=result.get("security_score", 0.0),
            is_blocked=result.get("is_blocked", False),
            block_reason=result.get("block_reason"),
            sanitized_input=result.get("sanitized_input"),
            sanitization_warnings=result.get("sanitization_warnings"),
            pii_detections=result.get("pii_detections"),
            redacted_input=result.get("redacted_input"),
            detected_threats=result.get("detected_threats")
        )
    except Exception as e:
        logger.error("Security analysis failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Security analysis failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {
        "status": "ok",
        "service": settings.OTEL_SERVICE_NAME,
        "version": settings.VERSION
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Clestiq Shield - Security Agent",
        "version": settings.VERSION,
        "status": "operational"
    }
