from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "Clestiq Shield - Gateway"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change_this_to_a_strong_secret_key"
    ALGORITHM: str = "HS256"

    # Datadog APM
    TELEMETRY_ENABLED: bool = True
    DD_SERVICE: str = "clestiq-shield-gateway"
    DD_ENV: str = "production"
    DD_VERSION: str = "1.0.0"
    DD_AGENT_HOST: str = "localhost"
    DD_DOGSTATSD_PORT: int = 8125
    DD_DOGSTATSD_SOCKET: str = ""

    # Sentinel Service (Input Security)
    SENTINEL_SERVICE_URL: str = "http://sentinel:8001"

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
