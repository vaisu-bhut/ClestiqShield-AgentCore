import logging
import sys
import structlog
from ddtrace import tracer, patch_all
from ddtrace.runtime import RuntimeMetrics

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


def setup_telemetry(app):
    """Configure Datadog APM and structured logging."""
    # Skip telemetry setup if disabled (e.g., in test environments)
    if not settings.TELEMETRY_ENABLED:
        log = structlog.get_logger()
        log.info("Telemetry disabled, skipping Datadog APM initialization")

        # Still configure basic structlog for tests
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return

    # Patch all supported libraries for automatic instrumentation
    # This includes FastAPI, httpx, langchain, etc.
    patch_all()

    # Enable Continuous Profiler for code performance analysis
    from ddtrace.profiling import Profiler

    profiler = Profiler()
    profiler.start()

    # Enable runtime metrics collection (CPU, memory, etc.)
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

    # Log initialization
    log = structlog.get_logger()
    log.info(
        "Datadog APM and Structlog initialized",
        service=settings.DD_SERVICE,
        env=settings.DD_ENV,
    )
