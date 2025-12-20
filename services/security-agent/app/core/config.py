from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Sentinel (Input Security)"
    VERSION: str = "1.0.0"

    # Datadog APM
    TELEMETRY_ENABLED: bool = True
    DD_SERVICE: str = "clestiq-shield-sentinel"
    DD_ENV: str = "production"
    DD_VERSION: str = "1.0.0"

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
    SECURITY_LLM_CHECK_ENABLED: bool = (
        False  # Disabled due to langchain_google_vertexai import hang
    )
    SECURITY_LLM_CHECK_THRESHOLD: float = 0.85

    # TOON Conversion Settings
    TOON_CONVERSION_ENABLED: bool = True

    # LLM Settings
    LLM_FORWARD_ENABLED: bool = True
    LLM_MODEL_NAME: str = "gemini-2.0-flash-exp"
    LLM_MAX_TOKENS: int = 8192

    # Guardian Service (Output Validation)
    GUARDIAN_SERVICE_URL: str = "http://guardian:8002"

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
