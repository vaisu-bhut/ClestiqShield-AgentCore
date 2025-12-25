from pydantic import BaseModel
from typing import Any, Dict, Optional


class SecuritySettings(BaseModel):
    """Unified security and validation settings."""

    # Privacy
    pii_masking: bool = False  # Enables both input redaction and output scanning

    # Input Security
    sanitize_input: bool = False
    detect_threats: bool = False  # Enables SQL, XSS, and Command injection detection

    # Output Validation
    content_filter: bool = False  # Toxicity and harmful content check
    hallucination_check: bool = False
    citation_check: bool = False
    tone_check: bool = False

    # Advanced / Misc
    toon_mode: bool = False  # Enables TOON conversion (in/out)
    enable_llm_forward: bool = False  # Should this be here? Yes.


class ChatRequest(BaseModel):
    """Simplified request schema."""

    query: str
    model: str = "gemini-3-flash-preview"
    moderation: str = "moderate"
    output_format: str = "json"
    max_output_tokens: Optional[int] = None
    settings: SecuritySettings = SecuritySettings()

    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class SentinelConfig(BaseModel):
    """Configuration for Sentinel (Input Security) features."""

    enable_sanitization: bool = False
    enable_pii_redaction: bool = False
    enable_xss_protection: bool = False
    enable_sql_injection_detection: bool = False
    enable_command_injection_detection: bool = False
    enable_toon_conversion: bool = False
    enable_llm_forward: bool = False


class GuardianConfig(BaseModel):
    """Configuration for Guardian (Output Validation) features."""

    enable_content_filter: bool = False
    enable_pii_scanner: bool = False
    enable_toon_decoder: bool = False
    enable_hallucination_detector: bool = False
    enable_citation_verifier: bool = False
    enable_tone_checker: bool = False
    enable_refusal_detector: bool = False
    enable_disclaimer_injector: bool = False


class GuardianMetrics(BaseModel):
    """Metrics returned by Guardian validation."""

    hallucination_detected: Optional[bool] = None
    citations_verified: Optional[bool] = None
    tone_compliant: Optional[bool] = None
    disclaimer_injected: Optional[bool] = None
    false_refusal_detected: Optional[bool] = None
    toxicity_score: Optional[float] = None


class SecurityMetrics(BaseModel):
    """Cumulative security metrics for the request."""

    security_score: float = 0.0
    tokens_saved: int = 0
    llm_tokens: Optional[Dict[str, int]] = None
    model_used: Optional[str] = None
    threats_detected: int = 0
    pii_redacted: int = 0
    processing_time_ms: float = 0.0
    guardian_metrics: Optional[GuardianMetrics] = None


class ChatResponse(BaseModel):
    """Response schema for /chat endpoint."""

    is_blocked: bool
    block_reason: Optional[str] = None
    llm_response: Optional[str] = None
    metrics: Optional[SecurityMetrics] = None
