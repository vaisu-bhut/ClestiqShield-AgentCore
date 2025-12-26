import logging
import sys
import structlog
from ddtrace import tracer
from datadog import initialize, statsd

from app.core.config import get_settings

settings = get_settings()


class TelemetryClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            # Initialize Datadog client
            options = {
                "statsd_host": settings.DD_AGENT_HOST,
                "statsd_port": settings.DD_DOGSTATSD_PORT,
            }

            # Prefer Socket if configured (Docker/K8s standard)
            if settings.DD_DOGSTATSD_SOCKET:
                options = {"statsd_socket_path": settings.DD_DOGSTATSD_SOCKET}

            initialize(**options)
            self._initialized = True

            # Use standard logger here to avoid circular deps or complex structlog init issues early on
            logging.getLogger("uvicorn").info(
                f"Telemetry initialized mode={'socket' if settings.DD_DOGSTATSD_SOCKET else 'udp'} "
                f"target={settings.DD_DOGSTATSD_SOCKET or f'{settings.DD_AGENT_HOST}:{settings.DD_DOGSTATSD_PORT}'}"
            )
        except Exception as e:
            logging.getLogger("uvicorn").error(
                f"Failed to initialize telemetry: {str(e)}"
            )

    def increment(self, metric: str, value: int = 1, tags: list[str] = None):
        """Increment a counter metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.increment(metric, tags=all_tags, value=value)
        except Exception as e:
            # Squelch errors to prevent app crash, but log warning
            logging.getLogger("uvicorn").warning(f"Failed to send metric {metric}: {e}")

    def gauge(self, metric: str, value: float, tags: list[str] = None):
        """Record a gauge metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.gauge(metric, value, tags=all_tags)
        except Exception as e:
            logging.getLogger("uvicorn").warning(f"Failed to send metric {metric}: {e}")

    def histogram(self, metric: str, value: float, tags: list[str] = None):
        """Record a histogram metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.histogram(metric, value, tags=all_tags)
        except Exception as e:
            logging.getLogger("uvicorn").warning(f"Failed to send metric {metric}: {e}")

    def _get_default_tags(self) -> list[str]:
        return [
            f"service:{settings.DD_SERVICE}",
            f"env:{settings.DD_ENV}",
            f"version:{settings.DD_VERSION}",
        ]


# Global instance
telemetry = TelemetryClient()


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
