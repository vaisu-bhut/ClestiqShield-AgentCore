"""
Guardian Metrics Module.

Tracks output validation, content filtering, and guardrails metrics for Datadog.
"""

from opentelemetry import metrics
from typing import Optional
import structlog

logger = structlog.get_logger()

_meter: Optional[metrics.Meter] = None


def get_meter() -> metrics.Meter:
    global _meter
    if _meter is None:
        _meter = metrics.get_meter("clestiq.guardian.agent", version="1.0.0")
    return _meter


class GuardianMetrics:
    """Singleton for Guardian-specific metrics."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if GuardianMetrics._initialized:
            return

        meter = get_meter()

        # Request metrics
        self.requests_total = meter.create_counter(
            name="guardian.requests_total",
            description="Total validation requests",
            unit="1",
        )

        self.requests_by_mode = meter.create_counter(
            name="guardian.requests_by_mode",
            description="Requests by moderation mode",
            unit="1",
        )

        # Content filtering metrics
        self.content_filtered = meter.create_counter(
            name="guardian.content_filtered",
            description="Content filtered by category",
            unit="1",
        )

        self.content_by_action = meter.create_counter(
            name="guardian.content_by_action",
            description="Content actions (block, warn, allow)",
            unit="1",
        )

        # PII leak detection
        self.pii_leaks_detected = meter.create_counter(
            name="guardian.pii_leaks_detected",
            description="PII leaks detected in LLM output",
            unit="1",
        )

        # TOON conversion
        self.toon_conversions = meter.create_counter(
            name="guardian.toon_conversions",
            description="TOON to JSON conversions",
            unit="1",
        )

        # Latency histograms
        self.validation_latency = meter.create_histogram(
            name="guardian.validation_latency_ms",
            description="Total validation latency",
            unit="ms",
        )

        self.content_filter_latency = meter.create_histogram(
            name="guardian.content_filter_latency_ms",
            description="Content filtering latency",
            unit="ms",
        )

        self.pii_scan_latency = meter.create_histogram(
            name="guardian.pii_scan_latency_ms",
            description="PII scanning latency",
            unit="ms",
        )

        GuardianMetrics._initialized = True
        logger.info("Guardian metrics initialized")

    def record_request(self, moderation_mode: str):
        self.requests_total.add(1)
        self.requests_by_mode.add(1, {"mode": moderation_mode})

    def record_content_filtered(self, category: str, action: str):
        self.content_filtered.add(1, {"category": category})
        self.content_by_action.add(1, {"action": action})

    def record_pii_leak(self, pii_type: str):
        self.pii_leaks_detected.add(1, {"pii_type": pii_type})

    def record_toon_conversion(self, success: bool):
        self.toon_conversions.add(1, {"success": str(success)})

    def record_latency(self, stage: str, latency_ms: float):
        if stage == "validation":
            self.validation_latency.record(latency_ms)
        elif stage == "content_filter":
            self.content_filter_latency.record(latency_ms)
        elif stage == "pii_scan":
            self.pii_scan_latency.record(latency_ms)


_guardian_metrics: Optional[GuardianMetrics] = None


def get_guardian_metrics() -> GuardianMetrics:
    global _guardian_metrics
    if _guardian_metrics is None:
        _guardian_metrics = GuardianMetrics()
    return _guardian_metrics
