# ── config.py ────────────────────────────────────────────────────────────────
# Central settings loaded from environment variables or .env file.
# Copy .env.example to .env and fill in your own values before running.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Verdant API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./verdant.db"

    # ── JWT ──────────────────────────────────────────────────────────────────
    # Generate a strong secret:  openssl rand -hex 32
    JWT_SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins for the frontend
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:5500,"
        "http://localhost:8000,"
        "http://127.0.0.1:8000,"
        "http://localhost:8001,"
        "http://127.0.0.1:8001,"
        "http://localhost:8002,"
        "http://127.0.0.1:8002"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
