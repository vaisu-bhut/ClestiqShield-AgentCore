from pydantic import BaseModel
from typing import Any, Dict, Optional


class ChatRequest(BaseModel):
    """Request schema for /chat endpoint."""

    input: Dict[str, Any]  # Contains: prompt, model, moderation, output_format
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class ChatResponse(BaseModel):
    """Response schema for /chat endpoint."""

    is_blocked: bool
    block_reason: Optional[str] = None
    llm_response: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None  # Basic metrics for gateway
