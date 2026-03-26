from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    DATABASE_URL: str

    GEMINI_API_KEY: str | None = None
    REDIS_URL: str | None = None
    UNG_API_URL: str | None = None
    UNG_API_KEY: str | None = None

    # Ingestion Target URLs
    AMFI_URL: str = "https://www.amfiindia.com/spages/NAVAll.txt"
    RSS_URLS: list[str] = [
        "https://www.moneycontrol.com/rss/business.xml",
        "https://www.livemint.com/rss/markets",
    ]
    SCREENER_BASE_URL: str = "https://www.screener.in/company/"

    # S3 / MinIO Storage Configuration
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "alpha-extractor-raw"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instantiate a global settings object
settings = Settings()
