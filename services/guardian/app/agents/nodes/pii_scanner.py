"""
PII Scanner Node.

Scans LLM output for accidental PII leaks.
"""

import re
import time
from typing import Dict, Any, List
import structlog

from app.core.metrics import get_guardian_metrics

logger = structlog.get_logger()


class OutputPIIScanner:
    """Scans LLM output for PII leaks."""

    # Same patterns as input PII detection
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CC_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b"
    )
    API_KEY_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")
    IP_ADDRESS_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

    @classmethod
    def scan(cls, text: str) -> List[Dict[str, Any]]:
        """Scan text for PII leaks."""
        if not text:
            return []

        leaks = []

        # SSN
        if cls.SSN_PATTERN.search(text):
            leaks.append({"type": "SSN", "severity": "high"})

        # Credit Card
        if cls.CC_PATTERN.search(text):
            leaks.append({"type": "CREDIT_CARD", "severity": "high"})

        # Email
        emails = cls.EMAIL_PATTERN.findall(text)
        if emails:
            leaks.append({"type": "EMAIL", "count": len(emails), "severity": "medium"})

        # Phone
        phones = cls.PHONE_PATTERN.findall(text)
        if phones:
            leaks.append({"type": "PHONE", "count": len(phones), "severity": "medium"})

        # API Keys
        if cls.API_KEY_PATTERN.search(text):
            leaks.append({"type": "API_KEY", "severity": "high"})

        # IP Address
        ips = cls.IP_ADDRESS_PATTERN.findall(text)
        if ips:
            leaks.append({"type": "IP_ADDRESS", "count": len(ips), "severity": "low"})

        return leaks

    @classmethod
    def redact(cls, text: str) -> str:
        """Redact PII from text."""
        if not text:
            return text

        text = cls.SSN_PATTERN.sub("[SSN_REDACTED]", text)
        text = cls.CC_PATTERN.sub("[CC_REDACTED]", text)
        text = cls.EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
        text = cls.PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        text = cls.API_KEY_PATTERN.sub("[API_KEY_REDACTED]", text)

        return text


async def pii_scanner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan LLM output for PII leaks and optionally redact.
    """
    metrics = get_guardian_metrics()
    start_time = time.perf_counter()

    llm_response = state.get("llm_response", "")

    if not llm_response:
        return {**state, "output_pii_leaks": [], "output_redacted": False}

    # Scan for leaks
    leaks = OutputPIIScanner.scan(llm_response)

    # Record metrics
    for leak in leaks:
        metrics.record_pii_leak(leak["type"])

    # Redact if high severity leaks found
    redacted = False
    high_severity = any(l.get("severity") == "high" for l in leaks)

    if high_severity:
        llm_response = OutputPIIScanner.redact(llm_response)
        redacted = True
        logger.warning("High severity PII leak detected and redacted", leaks=leaks)

    latency_ms = (time.perf_counter() - start_time) * 1000
    metrics.record_latency("pii_scan", latency_ms)

    logger.info(
        "PII scan complete",
        leaks_found=len(leaks),
        redacted=redacted,
        latency_ms=round(latency_ms, 2),
    )

    return {
        **state,
        "llm_response": llm_response,
        "output_pii_leaks": leaks,
        "output_redacted": redacted,
    }
