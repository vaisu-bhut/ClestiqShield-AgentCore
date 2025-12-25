from typing import Dict, Any, List, Optional
import time
import json
from datetime import datetime

from app.agents.state import AgentState
from app.core.metrics import get_security_metrics, MetricsDataBuilder
from app.agents.nodes.sanitizers import InputSanitizer, PIIRedactor
from app.agents.nodes.threat_detectors import ThreatDetector
import structlog

logger = structlog.get_logger()


def log_security_event(
    event_type: str,
    severity: str,
    policy_violated: List[str],
    threat_score: float = 0.0,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Log a SIEM-compatible security event.

    This creates a structured JSON log that can be ingested by SIEM tools
    (Splunk, ELK, Datadog Security, etc.) for compliance and threat monitoring.

    CRITICAL: This function MUST NOT log any PII or raw user input.
    """
    security_event = {
        "event_type": event_type,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "sentinel",
        "policy_violated": policy_violated,
        "threat_score": threat_score,
        "client_ip": client_ip,
        "user_agent": user_agent,
        # DO NOT include: user_input, payload, tokens, or any PII
    }

    # Use a specific logger channel for security events
    logger.warning(
        "SECURITY_EVENT",
        **security_event,
        # This makes it parseable as JSON for SIEM ingestion
        extra={"security_event": json.dumps(security_event)},
    )


async def security_check(state: AgentState) -> Dict[str, Any]:
    """
    Run security checks on the input with comprehensive metrics recording.
    """
    metrics = get_security_metrics()
    metrics_builder = MetricsDataBuilder()

    # Record request start
    metrics.record_request_start()
    request_start = time.perf_counter()

    user_input = (state.get("input") or {}).get("prompt", "")

    # Handle case where input is None or empty
    if not user_input:
        latency_ms = (time.perf_counter() - request_start) * 1000
        metrics.record_request_end(
            blocked=False, latency_ms=latency_ms, threat_score=0.0
        )
        return {
            "security_score": 0.0,
            "is_blocked": False,
            "block_reason": None,
            "sanitized_input": "",
            "sanitization_warnings": [],
            "pii_detections": [],
            "redacted_input": "",
            "detected_threats": [],
            "metrics_data": metrics_builder.build(),
            "client_ip": state.get("client_ip"),
            "user_agent": state.get("user_agent"),
        }

    # Initialize result
    result = {
        "security_score": 0.0,
        "is_blocked": False,
        "block_reason": None,
        "sanitized_input": None,
        "sanitization_warnings": [],
        "pii_detections": [],
        "redacted_input": None,
        "detected_threats": [],
        "client_ip": state.get("client_ip"),
        "user_agent": state.get("user_agent"),
    }

    try:
        # Get feature flags from state (injected by main.py based on simplified request)
        sentinel_config = state.get("sentinel_config")

        # Step 1: Input Sanitization (if enabled)
        if sentinel_config and sentinel_config.enable_sanitization:
            stage_start = time.perf_counter()
            sanitized_input, warnings = InputSanitizer.sanitize_input(user_input)
            stage_latency = (time.perf_counter() - stage_start) * 1000

            result["sanitized_input"] = sanitized_input
            result["sanitization_warnings"] = warnings
            user_input = sanitized_input

            # Record sanitization metrics
            metrics.record_stage_latency("sanitization", stage_latency)
            metrics_builder.add_latency("sanitization", stage_latency)

            if warnings:
                logger.info("Sanitization warnings", warnings=warnings)

        # Step 2: PII Detection and Pseudonymization (if enabled)
        pii_mapping = {}
        if sentinel_config and sentinel_config.enable_pii_redaction:
            stage_start = time.perf_counter()
            pseudonymized_input, pii_detections, pii_mapping = (
                PIIRedactor.pseudonymize_pii(user_input)
            )
            stage_latency = (time.perf_counter() - stage_start) * 1000

            result["pii_detections"] = pii_detections
            result["redacted_input"] = pseudonymized_input
            result["pii_mapping"] = pii_mapping
            user_input = pseudonymized_input

            # Record PII metrics
            metrics.record_stage_latency("pii_pseudonymization", stage_latency)
            metrics_builder.add_latency("pii_pseudonymization", stage_latency)

            for detection in pii_detections:
                pii_type = detection.get("type", "UNKNOWN")
                pii_count = detection.get("count", 1)
                metrics.record_pii_redaction(pii_type, pii_count)
                metrics_builder.add_pii(pii_type, pii_count)

            if pii_detections:
                # Zero-Trust Logging: Only log token count, NOT the actual PII or tokens
                logger.info(
                    "PII detected and pseudonymized",
                    pii_types=[d["type"] for d in pii_detections],
                    token_count=len(pii_mapping),
                )

        # Step 3: Threat Detection
        logger.info("Starting Threat Detection...")
        stage_start = time.perf_counter()
        threats = []

        # SQL Injection Detection
        if sentinel_config and sentinel_config.enable_sql_injection_detection:
            sql_threat = ThreatDetector.detect_sql_injection(user_input)
            if sql_threat["detected"]:
                threats.append(sql_threat)

        # XSS Detection
        if sentinel_config and sentinel_config.enable_xss_protection:
            xss_threat = ThreatDetector.detect_xss(user_input)
            if xss_threat["detected"]:
                threats.append(xss_threat)

        # Command Injection Detection
        if sentinel_config and sentinel_config.enable_command_injection_detection:
            cmd_threat = ThreatDetector.detect_command_injection(user_input)
            if cmd_threat["detected"]:
                threats.append(cmd_threat)

        # Path Traversal Detection (run if any threat detection enabled)
        if sentinel_config and (
            sentinel_config.enable_sql_injection_detection
            or sentinel_config.enable_xss_protection
            or sentinel_config.enable_command_injection_detection
        ):
            path_threat = ThreatDetector.detect_path_traversal(user_input)
            if path_threat["detected"]:
                threats.append(path_threat)

        # Record latency if any threat detection was run
        if sentinel_config and (
            sentinel_config.enable_sql_injection_detection
            or sentinel_config.enable_xss_protection
            or sentinel_config.enable_command_injection_detection
        ):
            stage_latency = (time.perf_counter() - stage_start) * 1000
            logger.info(f"Threat Detection completed in {stage_latency:.2f}ms")
            metrics.record_stage_latency("threat_detection", stage_latency)
            metrics_builder.add_latency("threat_detection", stage_latency)

        result["detected_threats"] = threats

        # Record attack metrics for threats
        for threat in threats:
            attack_type = threat.get("threat_type", "unknown")
            confidence = threat.get("confidence", 0.0)
            metrics.record_attack_prevented(attack_type)
            metrics_builder.add_attack(attack_type, confidence)

        # Block if high-confidence threats detected
        if threats:
            max_confidence = max(t["confidence"] for t in threats)
            if max_confidence >= 0.7:  # High confidence threat
                threat_types = [t["threat_type"] for t in threats]

                # SIEM-compatible Security Event Log
                log_security_event(
                    event_type="THREAT_BLOCKED",
                    severity="HIGH",
                    policy_violated=threat_types,
                    threat_score=max_confidence,
                    client_ip=state.get("client_ip"),
                    user_agent=state.get("user_agent"),
                )

                latency_ms = (time.perf_counter() - request_start) * 1000
                metrics.record_request_end(
                    blocked=True, latency_ms=latency_ms, threat_score=max_confidence
                )

                return {
                    **result,
                    "security_score": max_confidence,
                    "is_blocked": True,
                    "block_reason": f"Security threats detected: {', '.join(threat_types)}",
                    "metrics_data": metrics_builder.build(),
                }

        # Calculate final score from threat detection only (no LLM check)
        score = 0.0
        if threats:
            score = max(t["confidence"] for t in threats)

        # Record final request metrics
        latency_ms = (time.perf_counter() - request_start) * 1000
        metrics.record_request_end(
            blocked=False, latency_ms=latency_ms, threat_score=score
        )

        logger.info(
            "Security check complete",
            score=score,
            blocked=False,
            threats_count=len(threats),
            latency_ms=round(latency_ms, 2),
        )

        return {
            **result,
            "security_score": score,
            "is_blocked": False,
            "block_reason": None,
            "metrics_data": metrics_builder.build(),
        }

    except Exception as e:
        latency_ms = (time.perf_counter() - request_start) * 1000
        metrics.record_request_end(
            blocked=True, latency_ms=latency_ms, threat_score=1.0
        )

        logger.error("Security check failed", error=str(e), exc_info=True)
        # Fail safe: block if we can't verify
        return {
            **result,
            "security_score": 1.0,
            "is_blocked": True,
            "block_reason": "Security verification failed",
            "metrics_data": metrics_builder.build(),
        }
