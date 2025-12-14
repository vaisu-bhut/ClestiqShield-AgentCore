"""
Gateway request/response schemas.

Defines explicit typed schemas for the gateway API with model selection,
guardrails configuration, and detailed response metrics including token usage.
"""

from pydantic import BaseModel, Field
from typing import Optional


class GuardrailsConfig(BaseModel):
    """Guardrails configuration for security features."""

    content_filtering: bool = Field(
        default=True, description="Enable content moderation and filtering"
    )
    pii_detection: bool = Field(
        default=True, description="Enable PII detection and redaction"
    )
    threat_detection: bool = Field(
        default=True, description="Enable threat/injection detection"
    )

    # NEW: Advanced Guardian validation features
    hallucination_check: bool = Field(
        default=False, description="Enable hallucination detection using Judge LLM"
    )
    citation_verification: bool = Field(
        default=False, description="Enable citation and source verification"
    )
    brand_tone: Optional[str] = Field(
        default=None,
        description="Enforce brand tone: professional, casual, technical, or friendly",
    )
    auto_disclaimers: bool = Field(
        default=False,
        description="Automatically inject legal disclaimers for medical/financial advice",
    )
    false_refusal_check: bool = Field(
        default=False, description="Detect when LLM incorrectly refuses valid requests"
    )
    toxicity_threshold: float = Field(
        default=0.7, description="Toxicity threshold (0.0-1.0) for blocking responses"
    )


class GatewayRequest(BaseModel):
    """
    Enhanced gateway request with explicit fields.

    Example:
        {
            "query": "What is machine learning?",
            "model": "gemini-2.0-flash",
            "moderation": "moderate",
            "output_format": "json",
            "guardrails": {
                "content_filtering": true,
                "pii_detection": true,
                "threat_detection": true
            }
        }
    """

    query: str = Field(..., description="User query/prompt to process")
    model: str = Field(
        default="gemini-2.0-flash",
        description="LLM model to use (gemini-2.0-flash, gemini-2.0, etc.)",
    )
    moderation: str = Field(
        default="moderate",
        description="Content moderation level: strict, moderate, relaxed, or raw",
    )
    output_format: str = Field(
        default="json", description="Output format: json or toon"
    )
    guardrails: Optional[GuardrailsConfig] = Field(
        default=None, description="Optional guardrails configuration"
    )


class TokenUsage(BaseModel):
    """LLM token usage metrics."""

    input_tokens: int = Field(..., description="Number of input tokens consumed")
    output_tokens: int = Field(..., description="Number of output tokens generated")
    total_tokens: int = Field(..., description="Total tokens (input + output)")


class ResponseMetrics(BaseModel):
    """Detailed response metrics."""

    security_score: float = Field(
        default=0.0, description="Security risk score (0.0 = safe, 1.0 = high risk)"
    )
    tokens_saved: int = Field(
        default=0, description="Tokens saved via TOON compression"
    )
    token_usage: Optional[TokenUsage] = Field(
        default=None, description="LLM token usage breakdown"
    )
    model_used: Optional[str] = Field(
        default=None, description="Actual LLM model used for response"
    )
    threats_detected: int = Field(
        default=0, description="Number of threats/injections detected"
    )
    pii_redacted: int = Field(
        default=0, description="Number of PII items detected and redacted"
    )
    processing_time_ms: Optional[float] = Field(
        default=None, description="Total processing time in milliseconds"
    )

    # NEW: Guardian validation results
    hallucination_detected: Optional[bool] = Field(
        default=None, description="Whether hallucination was detected in LLM response"
    )
    citations_verified: Optional[bool] = Field(
        default=None, description="Whether citations were verified as authentic"
    )
    tone_compliant: Optional[bool] = Field(
        default=None, description="Whether response matches the specified brand tone"
    )
    disclaimer_injected: Optional[bool] = Field(
        default=None, description="Whether a legal disclaimer was automatically added"
    )
    false_refusal_detected: Optional[bool] = Field(
        default=None, description="Whether LLM incorrectly refused a valid request"
    )
    toxicity_score: Optional[float] = Field(
        default=None, description="Toxicity score from 0.0 (safe) to 1.0 (toxic)"
    )


class GatewayResponse(BaseModel):
    """
    Enhanced gateway response with detailed metrics.

    Example:
        {
            "response": "Machine learning is...",
            "app": "my-app",
            "metrics": {
                "security_score": 0.1,
                "tokens_saved": 0,
                "token_usage": {
                    "input_tokens": 15,
                    "output_tokens": 150,
                    "total_tokens": 165
                },
                "model_used": "gemini-2.0-flash",
                "threats_detected": 0,
                "pii_redacted": 0
            }
        }
    """

    response: Optional[str] = Field(
        default=None, description="LLM response content (null if blocked)"
    )
    app: str = Field(..., description="Application name that made the request")
    metrics: ResponseMetrics = Field(..., description="Detailed processing metrics")
