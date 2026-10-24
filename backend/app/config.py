"""Application settings, loaded from environment variables / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "SecureDeposit - AICTE FDR Portal API"
    ENV: str = "dev"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://fdr:fdr@localhost:5432/fdr_portal"

    # Auth
    JWT_SECRET: str = "dev-only-secret-change-me-0123456789abcdef"
    JWT_ALG: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    MAX_FAILED_LOGINS: int = 5

    # Documents (encrypted at rest with Fernet / AES-128-CBC + HMAC-SHA256)
    FILE_ENCRYPTION_KEY: str = ""  # leave empty in dev -> derived from JWT_SECRET
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_MB: int = 10

    # CORS (comma separated)
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Email (Mailpit in docker-compose catches everything at http://localhost:8025)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "SecureDeposit Portal <no-reply@securedeposit.local>"
    SMTP_STARTTLS: bool = False

    # SMS is simulated in the prototype (logged as SIMULATED)
    SMS_PROVIDER: str = "simulated"

    # OCR
    GOOGLE_VISION_API_KEY: str = ""  # optional; Tesseract is used when empty
    TESSERACT_CMD: str = ""  # e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe on Windows

    # Bank verification sandbox (simulated Account Aggregator style API)
    MOCK_BANK_API_KEY: str = "sandbox-bank-key"
    BANK_API_BASE_URL: str = ""  # set to call a real/remote bank API over HTTP instead of the in-process sandbox

    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    SCHEDULER_TZ: str = "Asia/Kolkata"

    # Demo helpers (time travel, reset). Turn OFF in production.
    DEMO_MODE: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
