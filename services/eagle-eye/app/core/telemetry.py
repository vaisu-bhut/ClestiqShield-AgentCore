import logging
import sys
import structlog
from ddtrace import tracer

from app.core.config import get_settings

settings = get_settings()


def add_datadog_trace_context(_, __, event_dict):
    """Add Datadog trace context to logs for correlation."""
    span = tracer.current_span()
    if span:
        event_dict["dd.trace_id"] = str(span.trace_id)
        event_dict["dd.span_id"] = str(span.span_id)
        event_dict["dd.service"] = span.service
        event_dict["dd.env"] = span.get_tag("env")
        event_dict["dd.version"] = span.get_tag("version")
    return event_dict


def setup_logging():
    """Configure structured logging with Datadog trace context."""
    if not settings.TELEMETRY_ENABLED:
        return

    # Enable Datadog instrumentation
    from ddtrace import patch_all
    from ddtrace.runtime import RuntimeMetrics
    from ddtrace.profiling import Profiler

    patch_all()

    # Enable Continuous Profiler
    profiler = Profiler()
    profiler.start()

    # Enable runtime metrics
    RuntimeMetrics.enable()

    # Configure Structlog with Datadog trace context
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_datadog_trace_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Standard Library Logging
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[stdout_handler],
    )

    # Force uvicorn logs to JSON format
    logging.getLogger("uvicorn.access").handlers = [stdout_handler]
    logging.getLogger("uvicorn.error").handlers = [stdout_handler]
