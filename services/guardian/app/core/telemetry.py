import logging
import sys
import structlog
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# HTTP Exporters
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Import OTLP Log components (HTTP)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider

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


def setup_telemetry(app):
    if not settings.TELEMETRY_ENABLED:
        log = structlog.get_logger()
        log.info("Telemetry disabled")
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

    import socket

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: settings.VERSION,
            ResourceAttributes.HOST_NAME: socket.gethostname(),
        }
    )

    # Tracing (HTTP)
    trace_provider = TracerProvider(resource=resource)
    # The HTTP exporter usually needs the full path: /v1/traces
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
    )
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics (HTTP)
    # /v1/metrics
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/metrics"
    )
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # --- OTLP Logging Setup (HTTP) ---
    # Create Logger Provider
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    # /v1/logs
    otlp_log_exporter = OTLPLogExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs"
    )

    # Add Batch Processor
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))

    # Configure Structlog
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

    # Force uvicorn logs to use OTLP handler
    logging.getLogger("uvicorn.access").handlers = [otlp_handler, stdout_handler]
    logging.getLogger("uvicorn.error").handlers = [otlp_handler, stdout_handler]

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=trace_provider, meter_provider=meter_provider
    )

    # Log initialization
    log = structlog.get_logger()
    log.info("Guardian telemetry initialized", service_name=settings.OTEL_SERVICE_NAME)
