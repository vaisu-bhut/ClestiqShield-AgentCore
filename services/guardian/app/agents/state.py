from typing import TypedDict, Any, Dict, Optional, List


class GuardianState(TypedDict):
    # Input from Sentinel
    llm_response: str
    moderation_mode: str  # strict, moderate, relaxed, raw
    output_format: str  # json or toon

    # Guardrails config (extended)
    guardrails: Optional[Dict[str, Any]]
    original_query: Optional[str]  # Pass from Sentinel for hallucination check

    # Content filtering
    content_filtered: bool
    content_warnings: Optional[List[str]]
    content_blocked: bool
    content_block_reason: Optional[str]

    # PII scanning
    output_pii_leaks: Optional[List[Dict[str, Any]]]
    output_redacted: bool

    # TOON decoding
    was_toon: bool

    # NEW: Hallucination Detection
    hallucination_detected: Optional[bool]
    hallucination_details: Optional[str]

    # NEW: Citation Verification
    citations_verified: Optional[bool]
    fake_citations: Optional[List[str]]

    # NEW: Brand Tone Compliance
    tone_compliant: Optional[bool]
    tone_violation_reason: Optional[str]

    # NEW: Disclaimer Injection
    disclaimer_injected: Optional[bool]
    disclaimer_text: Optional[str]

    # NEW: False Refusal Detection
    false_refusal_detected: Optional[bool]

    # NEW: Toxicity Scoring
    toxicity_score: Optional[float]
    toxicity_details: Optional[Dict[str, Any]]

    # Final output
    validated_response: Optional[str]
    validation_passed: bool

    # Metrics
    metrics_data: Optional[Dict[str, Any]]
