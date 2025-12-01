from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Security Agent"
    VERSION: str = "1.0.0"
    
    # OpenTelemetry
    TELEMETRY_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "clestiq-shield-security-agent"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"

    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-east1"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    # Security Settings
    SECURITY_SANITIZATION_ENABLED: bool = True
    SECURITY_PII_REDACTION_ENABLED: bool = True
    SECURITY_XSS_PROTECTION_ENABLED: bool = True
    SECURITY_SQL_INJECTION_DETECTION_ENABLED: bool = True
    SECURITY_COMMAND_INJECTION_DETECTION_ENABLED: bool = True
    SECURITY_LLM_CHECK_THRESHOLD: float = 0.85

    class Config:
        case_sensitive = True
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
