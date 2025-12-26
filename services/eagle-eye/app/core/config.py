from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "EagleEye - Auth & Management"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    # Defaulting to the shared db service
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/clestiq_shield"

    # JWT Auth
    SECRET_KEY: str = "change_this_to_a_strong_secret_key"  # In prod, use env var
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Datadog APM
    TELEMETRY_ENABLED: bool = True
    DD_SERVICE: str = "clestiq-shield-eagle-eye"
    DD_ENV: str = "production"
    DD_VERSION: str = "1.0.0"
    DD_AGENT_HOST: str = "datadog-agent"
    DD_DOGSTATSD_PORT: int = 8125
    DD_DOGSTATSD_SOCKET: str = ""

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
