from typing import TypedDict, Any, Dict, Optional

class AgentState(TypedDict):
    input: Dict[str, Any]
    security_score: float
    is_blocked: bool
    block_reason: Optional[str]
