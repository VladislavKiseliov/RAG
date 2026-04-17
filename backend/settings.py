# backend/config.py
from pydantic_settings import BaseSettings,SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),  # ← ищет в обоих местах
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # ──────────────────────────────────────────
    # Database
    # ──────────────────────────────────────────

    DATABASE_URL :str

    # ──────────────────────────────────────────
    # Authentication
    # ──────────────────────────────────────────
    SECRET_KEY  :str
    ALGORITHM   :str
    ACCESS_TOKEN_EXPIRE_MINUTES :int
    REFRESH_TOKEN_EXPIRE_DAYS   :int

settings = BackendSettings()
