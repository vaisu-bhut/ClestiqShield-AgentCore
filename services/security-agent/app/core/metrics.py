"""
Comprehensive metrics module for Datadog observability.

This module provides custom OpenTelemetry metrics for tracking:
- Attack prevention (by type)
- PII redactions (by type)
- Token usage and savings
- Request latency by stage
- Overall security request stats
"""

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, UpDownCounter
from typing import Dict, Any, Optional
import structlog
import time
from contextlib import contextmanager
from functools import wraps

logger = structlog.get_logger()

# Get the global meter
_meter: Optional[metrics.Meter] = None


def get_meter() -> metrics.Meter:
    """Get or create the global meter for security metrics."""
    global _meter
    if _meter is None:
        _meter = metrics.get_meter("clestiq.security.agent", version="1.0.0")
    return _meter


# ============================================================================
# COUNTERS - Aggregate totals
# ============================================================================


class SecurityMetrics:
    """Singleton class managing all security-related metrics."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SecurityMetrics._initialized:
            return

        meter = get_meter()

        # ---- Attack Prevention Metrics ----
        self.attacks_prevented = meter.create_counter(
            name="security.attacks_prevented",
            description="Total number of attacks prevented",
            unit="1",
        )

        self.attacks_by_type = meter.create_counter(
            name="security.attacks_by_type",
            description="Attacks prevented broken down by attack type",
            unit="1",
        )

        # ---- PII Redaction Metrics ----
        self.pii_redactions = meter.create_counter(
            name="security.pii_redactions",
            description="Total PII items redacted",
            unit="1",
        )

        self.pii_by_type = meter.create_counter(
            name="security.pii_by_type",
            description="PII redactions by type (SSN, CC, EMAIL, PHONE, etc.)",
            unit="1",
        )

        # ---- Token Metrics ----
        self.tokens_saved = meter.create_counter(
            name="security.tokens_saved",
            description="Tokens saved by TOON conversion",
            unit="1",
        )

        self.llm_tokens_input = meter.create_counter(
            name="security.llm_tokens_input",
            description="Input tokens sent to LLM",
            unit="1",
        )

        self.llm_tokens_output = meter.create_counter(
            name="security.llm_tokens_output",
            description="Output tokens received from LLM",
            unit="1",
        )

        self.llm_tokens_total = meter.create_counter(
            name="security.llm_tokens_total",
            description="Total tokens used (input + output)",
            unit="1",
        )

        # ---- Request Metrics ----
        self.requests_total = meter.create_counter(
            name="security.requests_total",
            description="Total security analysis requests",
            unit="1",
        )

        self.requests_blocked = meter.create_counter(
            name="security.requests_blocked",
            description="Requests blocked by security checks",
            unit="1",
        )

        self.requests_passed = meter.create_counter(
            name="security.requests_passed",
            description="Requests that passed security checks",
            unit="1",
        )

        # ---- Latency Histograms ----
        self.request_latency = meter.create_histogram(
            name="security.request_latency_ms",
            description="End-to-end request latency in milliseconds",
            unit="ms",
        )

        self.sanitization_latency = meter.create_histogram(
            name="security.sanitization_latency_ms",
            description="Input sanitization latency in milliseconds",
            unit="ms",
        )

        self.pii_detection_latency = meter.create_histogram(
            name="security.pii_detection_latency_ms",
            description="PII detection and redaction latency in milliseconds",
            unit="ms",
        )

        self.threat_detection_latency = meter.create_histogram(
            name="security.threat_detection_latency_ms",
            description="Threat detection latency in milliseconds",
            unit="ms",
        )

        self.llm_check_latency = meter.create_histogram(
            name="security.llm_check_latency_ms",
            description="LLM security check latency in milliseconds",
            unit="ms",
        )

        self.toon_conversion_latency = meter.create_histogram(
            name="security.toon_conversion_latency_ms",
            description="TOON conversion latency in milliseconds",
            unit="ms",
        )

        self.llm_response_latency = meter.create_histogram(
            name="security.llm_response_latency_ms",
            description="LLM response generation latency in milliseconds",
            unit="ms",
        )

        # ---- Score Distribution ----
        self.threat_score_distribution = meter.create_histogram(
            name="security.threat_score",
            description="Distribution of threat scores (0.0-1.0)",
            unit="1",
        )

        # ---- Active Requests Gauge ----
        self.active_requests = meter.create_up_down_counter(
            name="security.active_requests",
            description="Currently processing requests",
            unit="1",
        )

        SecurityMetrics._initialized = True
        logger.info("Security metrics initialized")

    # ========================================================================
    # Recording Methods
    # ========================================================================

    def record_attack_prevented(self, attack_type: str, count: int = 1):
        """Record an attack that was prevented."""
        self.attacks_prevented.add(count)
        self.attacks_by_type.add(count, {"attack_type": attack_type})
        logger.info("Attack prevented", attack_type=attack_type, count=count)

    def record_pii_redaction(self, pii_type: str, count: int = 1):
        """Record PII redaction."""
        self.pii_redactions.add(count)
        self.pii_by_type.add(count, {"pii_type": pii_type})
        logger.debug("PII redacted", pii_type=pii_type, count=count)

    def record_tokens_saved(self, tokens: int, conversion_type: str = "toon"):
        """Record tokens saved by conversion."""
        self.tokens_saved.add(tokens, {"conversion_type": conversion_type})
        logger.debug("Tokens saved", tokens=tokens, conversion_type=conversion_type)

    def record_llm_tokens(self, input_tokens: int, output_tokens: int):
        """Record LLM token usage."""
        total = input_tokens + output_tokens
        self.llm_tokens_input.add(input_tokens)
        self.llm_tokens_output.add(output_tokens)
        self.llm_tokens_total.add(total)
        logger.info(
            "LLM tokens used", input=input_tokens, output=output_tokens, total=total
        )

    def record_request_start(self):
        """Record a new request starting."""
        self.requests_total.add(1)
        self.active_requests.add(1)

    def record_request_end(
        self,
        blocked: bool,
        latency_ms: float,
        threat_score: float = 0.0,
        block_reason: Optional[str] = None,
    ):
        """
        Record request completion with detailed tags for Datadog observability.

        Args:
            blocked: Whether the request was blocked
            latency_ms: Total processing latency
            threat_score: Threat confidence score (0.0-1.0)
            block_reason: Specific reason for blocking (e.g., 'sql_injection', 'xss')
        """
        self.active_requests.add(-1)

        # Prepare tags for detailed filtering in Datadog
        tags = {
            "security_status": "blocked" if blocked else "passed",
        }

        if blocked and block_reason:
            # Normalize block reason to a tag-safe identifier
            normalized_reason = block_reason.lower().replace(" ", "_").replace(":", "")
            tags["block_reason"] = normalized_reason

        # Record metrics with tags
        self.request_latency.record(latency_ms, tags)
        self.threat_score_distribution.record(threat_score, tags)

        if blocked:
            self.requests_blocked.add(1, tags)
        else:
            self.requests_passed.add(1, tags)

        logger.info(
            "Request completed",
            **tags,
            latency_ms=round(latency_ms, 2),
            threat_score=round(threat_score, 4),
        )

    def record_stage_latency(self, stage: str, latency_ms: float):
        """Record latency for a specific processing stage."""
        stage_histograms = {
            "sanitization": self.sanitization_latency,
            "pii_detection": self.pii_detection_latency,
            "pii_pseudonymization": self.pii_detection_latency,  # Use same histogram
            "threat_detection": self.threat_detection_latency,
            "llm_check": self.llm_check_latency,
            "toon_conversion": self.toon_conversion_latency,
            "llm_response": self.llm_response_latency,
        }

        histogram = stage_histograms.get(stage)
        if histogram:
            histogram.record(latency_ms)
        else:
            logger.warning("Unknown stage for latency recording", stage=stage)

        histogram = stage_histograms.get(stage)
        if histogram:
            histogram.record(latency_ms)
        else:
            logger.warning("Unknown stage for latency recording", stage=stage)


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
    """Context manager to track latency of a code block."""
    metrics = get_security_metrics()
    start_time = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_stage_latency(stage, latency_ms)


def track_stage(stage: str):
    """Decorator to track latency of a function."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with track_latency(stage):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with track_latency(stage):
                return func(*args, **kwargs)

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
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
