"""
Comprehensive metrics module for Datadog observability.

NOTE: OpenTelemetry removed - using Datadog APM only. This module provides
no-op implementations to maintain API compatibility.
"""

from typing import Dict, Any, Optional
import structlog
import time
from contextlib import contextmanager
from functools import wraps

logger = structlog.get_logger()


class NoOpMetric:
    """No-op metric that does nothing but maintains API compatibility."""

    def add(self, value, attributes=None):
        pass

    def record(self, value, attributes=None):
        pass


class SecurityMetrics:
    """Singleton class managing all security-related metrics (no-op - using Datadog APM)."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SecurityMetrics._initialized:
            return

        # All metrics are no-ops now - Datadog APM provides automatic metrics
        self.attacks_prevented = NoOpMetric()
        self.attacks_by_type = NoOpMetric()
        self.pii_redactions = NoOpMetric()
        self.pii_by_type = NoOpMetric()
        self.tokens_saved = NoOpMetric()
        self.llm_tokens_input = NoOpMetric()
        self.llm_tokens_output = NoOpMetric()
        self.llm_tokens_total = NoOpMetric()
        self.requests_total = NoOpMetric()
        self.requests_blocked = NoOpMetric()
        self.requests_passed = NoOpMetric()
        self.request_latency = NoOpMetric()
        self.sanitization_latency = NoOpMetric()
        self.pii_detection_latency = NoOpMetric()
        self.threat_detection_latency = NoOpMetric()
        self.llm_check_latency = NoOpMetric()
        self.toon_conversion_latency = NoOpMetric()
        self.llm_response_latency = NoOpMetric()
        self.threat_score_distribution = NoOpMetric()
        self.active_requests = NoOpMetric()

        SecurityMetrics._initialized = True
        logger.info("Security metrics initialized (no-op - using Datadog APM)")

    def record_attack_prevented(self, attack_type: str, count: int = 1):
        """Record an attack that was prevented (no-op)."""
        logger.info("Attack prevented", attack_type=attack_type, count=count)

    def record_pii_redaction(self, pii_type: str, count: int = 1):
        """Record PII redaction (no-op)."""
        logger.debug("PII redacted", pii_type=pii_type, count=count)

    def record_tokens_saved(self, tokens: int, conversion_type: str = "toon"):
        """Record tokens saved by conversion (no-op)."""
        logger.debug("Tokens saved", tokens=tokens, conversion_type=conversion_type)

    def record_llm_tokens(self, input_tokens: int, output_tokens: int):
        """Record LLM token usage (no-op)."""
        total = input_tokens + output_tokens
        logger.info(
            "LLM tokens used", input=input_tokens, output=output_tokens, total=total
        )

    def record_request_start(self):
        """Record a new request starting (no-op)."""
        pass

    def record_request_end(
        self,
        blocked: bool,
        latency_ms: float,
        threat_score: float = 0.0,
        block_reason: Optional[str] = None,
    ):
        """Record request completion (no-op)."""
        tags = {"security_status": "blocked" if blocked else "passed"}
        if blocked and block_reason:
            normalized_reason = block_reason.lower().replace(" ", "_").replace(":", "")
            tags["block_reason"] = normalized_reason

        logger.info(
            "Request completed",
            **tags,
            latency_ms=round(latency_ms, 2),
            threat_score=round(threat_score, 4),
        )

    def record_stage_latency(self, stage: str, latency_ms: float):
        """Record latency for a specific processing stage (no-op)."""
        pass


# Global metrics instance
_security_metrics: Optional[SecurityMetrics] = None


def get_security_metrics() -> SecurityMetrics:
    """Get the global SecurityMetrics instance."""
    global _security_metrics
    if _security_metrics is None:
        _security_metrics = SecurityMetrics()
    return _security_metrics


# ============================================================================
# Decorators and Context Managers for Easy Instrumentation
# ============================================================================


@contextmanager
def track_latency(stage: str):
    """Context manager to track latency of a code block (no-op)."""
    metrics = get_security_metrics()
    start_time = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_stage_latency(stage, latency_ms)


def track_stage(stage: str):
    """Decorator to track latency of a function (no-op)."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with track_latency(stage):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with track_latency(stage):
                return func(*args, **kwargs)

        if hasattr(func, "__code") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# Metrics Data Builder for Response
# ============================================================================


class MetricsDataBuilder:
    """Builder for collecting metrics data during request processing."""

    def __init__(self):
        self.start_time = time.perf_counter()
        self.data: Dict[str, Any] = {
            "attacks_detected": [],
            "pii_redacted": [],
            "tokens_saved": 0,
            "llm_tokens": {"input": 0, "output": 0, "total": 0},
            "latencies_ms": {},
        }

    def add_attack(self, attack_type: str, confidence: float):
        """Add detected attack."""
        self.data["attacks_detected"].append(
            {"type": attack_type, "confidence": confidence}
        )

    def add_pii(self, pii_type: str, count: int):
        """Add PII redaction."""
        self.data["pii_redacted"].append({"type": pii_type, "count": count})

    def set_tokens_saved(self, tokens: int):
        """Set tokens saved by TOON conversion."""
        self.data["tokens_saved"] = tokens

    def set_llm_tokens(self, input_tokens: int, output_tokens: int):
        """Set LLM token usage."""
        self.data["llm_tokens"] = {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }

    def add_latency(self, stage: str, latency_ms: float):
        """Add latency measurement for a stage."""
        self.data["latencies_ms"][stage] = round(latency_ms, 2)

    def get_total_latency_ms(self) -> float:
        """Get total elapsed time since builder creation."""
        return (time.perf_counter() - self.start_time) * 1000

    def build(self) -> Dict[str, Any]:
        """Build the final metrics data dict."""
        self.data["total_latency_ms"] = round(self.get_total_latency_ms(), 2)
        return self.data
