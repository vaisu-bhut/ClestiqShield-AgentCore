from typing import TypedDict, Any, Dict, Optional, List


class AgentState(TypedDict):
    input: Dict[str, Any]
    security_score: float
    is_blocked: bool
    block_reason: Optional[str]

    # Sanitization
    sanitized_input: Optional[str]
    sanitization_warnings: Optional[List[str]]

    # PII Redaction
    pii_detections: Optional[List[Dict[str, Any]]]
    redacted_input: Optional[str]

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

    # Metrics Data (for response payload)
    metrics_data: Optional[Dict[str, Any]]

    # Metadata
    client_ip: Optional[str]
    user_agent: Optional[str]
