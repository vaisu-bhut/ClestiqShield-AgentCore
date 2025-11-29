from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # OpenTelemetry
    OTEL_SERVICE_NAME: str = "clestiq-shield-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"

    # Datadog (Optional, used by OTel Collector but present in .env)
    DD_API_KEY: str | None = None
    DD_SITE: str | None = None

    # Google Cloud / Vertex AI
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-east1"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None


    class Config:
        case_sensitive = True
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
