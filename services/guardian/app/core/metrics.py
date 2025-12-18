"""
Guardian Metrics Module.

Tracks output validation, content filtering, and guardrail metrics for Datadog.
NOTE: OpenTelemetry removed - using Datadog APM only. This module provides
no-op implementations to maintain API compatibility.
"""

from typing import Optional
import structlog

logger = structlog.get_logger()


class NoOpMetric:
    """No-op metric that does nothing but maintains API compatibility."""

    def add(self, value, attributes=None):
        pass

    def record(self, value, attributes=None):
        pass


class GuardianMetrics:
    """Singleton for Guardian-specific metrics (no-op - using Datadog APM instead)."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if GuardianMetrics._initialized:
            return

        # All metrics are no-ops now - Datadog APM provides automatic metrics
        self.requests_total = NoOpMetric()
        self.requests_by_mode = NoOpMetric()
        self.content_filtered = NoOpMetric()
        self.content_by_action = NoOpMetric()
        self.pii_leaks_detected = NoOpMetric()
        self.toon_conversions = NoOpMetric()
        self.validation_latency = NoOpMetric()
        self.content_filter_latency = NoOpMetric()
        self.pii_scan_latency = NoOpMetric()

        GuardianMetrics._initialized = True
        logger.info("Guardian metrics initialized (no-op - using Datadog APM)")

    def record_request(self, moderation_mode: str):
        pass  # No-op

    def record_content_filtered(self, category: str, action: str):
        pass  # No-op

    def record_pii_leak(self, pii_type: str):
        pass  # No-op

    def record_toon_conversion(self, success: bool):
        pass  # No-op

    def record_latency(self, stage: str, latency_ms: float):
        pass  # No-op


_guardian_metrics: Optional[GuardianMetrics] = None


def get_guardian_metrics() -> GuardianMetrics:
    global _guardian_metrics
    if _guardian_metrics is None:
        _guardian_metrics = GuardianMetrics()
    return _guardian_metrics
