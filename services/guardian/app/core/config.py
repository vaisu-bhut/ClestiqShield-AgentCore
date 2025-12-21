from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Guardian (Output Validation)"
    VERSION: str = "1.0.0"

    # Datadog APM
    TELEMETRY_ENABLED: bool = True
    DD_SERVICE: str = "clestiq-shield-guardian"
    DD_ENV: str = "production"
    DD_VERSION: str = "1.0.0"

    # Gemini AI Studio
    GEMINI_API_KEY: str

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
