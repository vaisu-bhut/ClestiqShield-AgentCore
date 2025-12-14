from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ValidateRequest(BaseModel):
    """Request schema for /validate endpoint."""

    llm_response: str
    moderation_mode: str = "moderate"  # strict, moderate, relaxed, raw
    output_format: str = "json"  # json or toon

    # NEW: Extended guardrails
    guardrails: Optional[Dict[str, Any]] = None
    original_query: Optional[str] = None  # For hallucination check


class ValidateResponse(BaseModel):
    """Response schema for /validate endpoint."""

    validated_response: Optional[str] = None
    validation_passed: bool

    # Existing fields
    content_blocked: bool = False
    content_block_reason: Optional[str] = None
    content_warnings: Optional[List[str]] = None
    output_pii_leaks: Optional[List[Dict[str, Any]]] = None
    output_redacted: bool = False
    was_toon: bool = False

    # NEW: Advanced validation results
    hallucination_detected: Optional[bool] = None
    hallucination_details: Optional[str] = None
    citations_verified: Optional[bool] = None
    fake_citations: Optional[List[str]] = None
    tone_compliant: Optional[bool] = None
    tone_violation_reason: Optional[str] = None
    disclaimer_injected: Optional[bool] = None
    disclaimer_text: Optional[str] = None
    false_refusal_detected: Optional[bool] = None
    toxicity_score: Optional[float] = None
    toxicity_details: Optional[Dict[str, Any]] = None

    metrics: Optional[Dict[str, Any]] = None
