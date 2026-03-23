from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    DATABASE_URL: str

    GEMINI_API_KEY: str | None = None
    REDIS_URL: str | None = None
    UNG_API_URL: str | None = None
    UNG_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instantiate a global settings object
settings = Settings()
