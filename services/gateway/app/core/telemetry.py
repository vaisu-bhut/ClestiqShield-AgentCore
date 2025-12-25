import structlog
from datadog import initialize, statsd
from app.core.config import get_settings

logger = structlog.get_logger()
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

            logger.info(
                "Telemetry initialized",
                mode="socket" if settings.DD_DOGSTATSD_SOCKET else "udp",
                target=settings.DD_DOGSTATSD_SOCKET
                or f"{settings.DD_AGENT_HOST}:{settings.DD_DOGSTATSD_PORT}",
            )
        except Exception as e:
            logger.error("Failed to initialize telemetry", error=str(e))

    def increment(self, metric: str, value: int = 1, tags: list[str] = None):
        """Increment a counter metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.increment(metric, tags=all_tags, value=value)
        except Exception as e:
            logger.warning(f"Failed to send metric {metric}", error=str(e))

    def gauge(self, metric: str, value: float, tags: list[str] = None):
        """Record a gauge metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.gauge(metric, value, tags=all_tags)
        except Exception as e:
            logger.warning(f"Failed to send metric {metric}", error=str(e))

    def histogram(self, metric: str, value: float, tags: list[str] = None):
        """Record a histogram metric."""
        if not settings.TELEMETRY_ENABLED:
            return

        try:
            all_tags = self._get_default_tags() + (tags or [])
            statsd.histogram(metric, value, tags=all_tags)
        except Exception as e:
            logger.warning(f"Failed to send metric {metric}", error=str(e))

    def _get_default_tags(self) -> list[str]:
        return [
            f"service:{settings.DD_SERVICE}",
            f"env:{settings.DD_ENV}",
            f"version:{settings.DD_VERSION}",
        ]


# Global instance
telemetry = TelemetryClient()
