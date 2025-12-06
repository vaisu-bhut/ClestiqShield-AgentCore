import logging
import structlog
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

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

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: settings.VERSION,
        }
    )

    # Tracing
    trace_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True
    )
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True
    )
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Logging
    import os
    import sys

    os.makedirs("logs", exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []

    file_handler = logging.FileHandler("logs/guardian.log")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(stream_handler)

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

    LoggingInstrumentor().instrument(set_logging_format=False)
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=trace_provider, meter_provider=meter_provider
    )

    log = structlog.get_logger()
    log.info("Guardian telemetry initialized", service_name=settings.OTEL_SERVICE_NAME)
