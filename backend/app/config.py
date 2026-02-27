"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./deals.db"

    # JWT
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_expiry_minutes: int = 60
    jwt_algorithm: str = "HS256"

    # CORS
    cors_origins: str = "*"

    # API
    api_version: str = "v1"
    log_level: str = "info"
    env: str = "development"

    # Upload
    max_upload_size_mb: int = 100
    upload_dir: str = "./uploads"

    # Anthropic API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Engine password gate
    engine_password: str = "crelytic2026"
    secret_key: str = "change-me-to-a-random-32-char-string-in-production"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
