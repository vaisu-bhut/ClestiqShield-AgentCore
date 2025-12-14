"""
False Refusal Detector Node.

Detects when the LLM incorrectly refuses to answer a legitimate question.
"""

import re
import time
from typing import Dict, Any, List
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()


class RefusalDetector:
    """Detects LLM refusals."""

    # Common refusal patterns
    REFUSAL_PATTERNS = [
        re.compile(r"I (cannot|can't|am unable to|won't)", re.IGNORECASE),
        re.compile(r"I (don't|do not) have (access|the ability)", re.IGNORECASE),
        re.compile(r"(Sorry|Apologies),? (I|but I) (cannot|can't)", re.IGNORECASE),
        re.compile(r"I'm not (able|allowed|permitted)", re.IGNORECASE),
        re.compile(r"as an AI", re.IGNORECASE),
        re.compile(r"I don't actually (have|know|provide)", re.IGNORECASE),
    ]

    @classmethod
    def detect_refusal(cls, text: str) -> bool:
        """Check if text contains refusal patterns."""
        for pattern in cls.REFUSAL_PATTERNS:
            if pattern.search(text):
                return True
        return False


async def refusal_detector_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect false refusals (LLM refusing valid requests).
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")
    guardrails = state.get("guardrails") or {}

    # Check if false_refusal_check is enabled
    if not guardrails.get("false_refusal_check", False):
        return state

    if not llm_response:
        return state

    try:
        refusal_detected = RefusalDetector.detect_refusal(llm_response)

        # If refusal is detected, it's a potential false refusal
        # (since Sentinel already blocked truly harmful requests)
        if refusal_detected:
            logger.warning(
                "Potential false refusal detected", response_preview=llm_response[:100]
            )

        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_latency("refusal_detection", latency_ms)

        logger.info(
            "Refusal detection complete",
            detected=refusal_detected,
            latency_ms=round(latency_ms, 2),
        )

        return {
            **state,
            "false_refusal_detected": refusal_detected,
        }

    except Exception as e:
        logger.error("Refusal detection failed", error=str(e))
        return state
