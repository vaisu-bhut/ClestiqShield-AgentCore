from typing import TypedDict, Any, Dict, Optional, List


class GuardianState(TypedDict):
    # Input from Sentinel
    llm_response: str
    moderation_mode: str  # strict, moderate, relaxed, raw
    output_format: str  # json or toon

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

    # Final output
    validated_response: Optional[str]
    validation_passed: bool

    # Metrics
    metrics_data: Optional[Dict[str, Any]]
