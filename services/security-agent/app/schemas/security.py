from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class SecurityAnalysisRequest(BaseModel):
    """Request schema for security analysis"""
    input: Dict[str, Any]
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

class SecurityAnalysisResponse(BaseModel):
    """Response schema for security analysis"""
    security_score: float
    is_blocked: bool
    block_reason: Optional[str] = None
    sanitized_input: Optional[str] = None
    sanitization_warnings: Optional[List[str]] = None
    pii_detections: Optional[List[Dict[str, Any]]] = None
    redacted_input: Optional[str] = None
    detected_threats: Optional[List[Dict[str, Any]]] = None
