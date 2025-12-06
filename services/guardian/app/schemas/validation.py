from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ValidateRequest(BaseModel):
    """Request schema for /validate endpoint."""

    llm_response: str
    moderation_mode: str = "moderate"  # strict, moderate, relaxed, raw
    output_format: str = "json"  # json or toon


class ValidateResponse(BaseModel):
    """Response schema for /validate endpoint."""

    validated_response: Optional[str] = None
    validation_passed: bool
    content_blocked: bool = False
    content_block_reason: Optional[str] = None
    content_warnings: Optional[List[str]] = None
    output_pii_leaks: Optional[List[Dict[str, Any]]] = None
    output_redacted: bool = False
    was_toon: bool = False
    metrics: Optional[Dict[str, Any]] = None
