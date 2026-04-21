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

    # CORS — set CORS_ORIGINS in .env for production (e.g. "https://crelytic.ai,https://engine.crelytic.ai")
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    # API
    api_version: str = "v1"
    log_level: str = "info"
    env: str = "development"

    # Upload
    max_upload_size_mb: int = 100
    upload_dir: str = "./uploads"

    # Anthropic API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_extraction_model: str = "claude-sonnet-4-20250514"

    # Auth
    secret_key: str = "change-me-to-a-random-32-char-string-in-production"
    admin_email: str = ""
    admin_password: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_starter_price_id: str = ""
    stripe_pro_price_id: str = ""
    stripe_unlimited_price_id: str = ""

    # Email (Resend) — first-deal feedback email (transactional sender: jonathan@crelytic.ai)
    resend_api_key: str = ""
    email_from: str = "jonathan@crelytic.ai"
    email_reply_to: str = "jonathan@crelytic.ai"
    feedback_base_url: str = "https://engine.crelytic.ai"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
