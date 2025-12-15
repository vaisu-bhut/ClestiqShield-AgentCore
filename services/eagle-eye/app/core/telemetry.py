import logging
import sys
import structlog
from opentelemetry import trace

# Import OTLP Log components (HTTP)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# HTTP Log Exporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from app.core.config import get_settings

settings = get_settings()


def add_open_telemetry_spans(_, __, event_dict):
    span = trace.get_current_span()
    if not span.is_recording():
        event_dict["span"] = None
        event_dict["trace"] = None
        return event_dict

    ctx = span.get_span_context()
    event_dict["span_id"] = format(ctx.span_id, "016x")
    event_dict["trace_id"] = format(ctx.trace_id, "032x")
    return event_dict


def setup_logging():
    if not settings.TELEMETRY_ENABLED:
        return

    # Create Resource
    import socket

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: settings.VERSION,
            ResourceAttributes.HOST_NAME: socket.gethostname(),
        }
    )

    # --- OTLP Logging Setup ---
    # Create Logger Provider
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    # Create OTLP Log Exporter (HTTP)
    # The endpoint should be full URL for HTTP exporter e.g. http://otel-collector:4318/v1/logs
    # But often the exporter appends /v1/logs if missing.
    # Let's trust the default behavior of the HTTP exporter with the base endpoint.
    otlp_log_exporter = OTLPLogExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs"
    )

    # Add Batch Processor
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))

    # Output logs to stdout as JSON using structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_open_telemetry_spans,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Standard Library Logging
    otlp_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[otlp_handler, stdout_handler],
    )
