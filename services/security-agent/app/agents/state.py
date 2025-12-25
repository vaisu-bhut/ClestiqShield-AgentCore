from typing import TypedDict, Any, Dict, Optional, List


class AgentState(TypedDict):
    input: Dict[str, Any]
    security_score: float
    is_blocked: bool
    block_reason: Optional[str]

    # Sanitization
    sanitized_input: Optional[str]
    sanitization_warnings: Optional[List[str]]

    # PII Redaction/Pseudonymization
    pii_detections: Optional[List[Dict[str, Any]]]
    redacted_input: Optional[str]
    pii_mapping: Optional[
        Dict[str, str]
    ]  # Token -> Original value map for depseudonymization

    # Threat Detection
    detected_threats: Optional[List[Dict[str, Any]]]

    # TOON Conversion
    toon_query: Optional[str]
    token_savings: Optional[int]

    # LLM Response
    llm_response: Optional[str]
    llm_tokens_used: Optional[Dict[str, int]]
    llm_error: Optional[str]
    model_used: Optional[str]

    # Guardian Validation Results
    guardian_validation: Optional[Dict[str, Any]]

    # Metrics Data (for response payload)
    metrics_data: Optional[Dict[str, Any]]

    # Metadata
    client_ip: Optional[str]
    user_agent: Optional[str]

    # Request object (for feature flags)
    request: Optional[Any]  # ChatRequest object

    # Internal Configs
    sentinel_config: Optional[Any]
    guardian_config: Optional[Any]

    # Detailed Guardian Metrics (Flattened for easier access)
    hallucination_detected: Optional[bool]
    citations_verified: Optional[bool]
    tone_compliant: Optional[bool]
    disclaimer_injected: Optional[bool]
    false_refusal_detected: Optional[bool]
    toxicity_score: Optional[float]

    # Security LLM Check Result
    security_llm_check: Optional[Dict[str, Any]]
