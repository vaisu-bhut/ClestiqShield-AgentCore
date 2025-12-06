from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Guardian (Output Validation)"
    VERSION: str = "1.0.0"

    # OpenTelemetry
    TELEMETRY_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "clestiq-shield-guardian"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"

    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-east1"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    # Moderation Settings
    DEFAULT_MODERATION_MODE: str = "moderate"  # strict, moderate, relaxed, raw

    # Content Filtering Thresholds
    HARMFUL_CONTENT_THRESHOLD: float = 0.7
    INAPPROPRIATE_CONTENT_THRESHOLD: float = 0.6
    SENSITIVE_CONTENT_THRESHOLD: float = 0.5

    # PII Detection in Output
    OUTPUT_PII_DETECTION_ENABLED: bool = True

    # Response Format
    AUTO_CONVERT_TOON_TO_JSON: bool = True

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
