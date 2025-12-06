from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Gateway"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # OpenTelemetry
    TELEMETRY_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "clestiq-shield-gateway"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"

    # Sentinel Service (Input Security)
    SENTINEL_SERVICE_URL: str = "http://sentinel:8001"

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
