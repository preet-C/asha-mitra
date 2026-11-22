# ASHA Mitra — config loader
# Reads all settings from backend/.env via pydantic-settings.
# Never import this in frontend. Never print SECRET values.

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "dev"
    GNANI_API_KEY: str = ""
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    DATABASE_URL: str = ""        # empty = in-memory repo
    CORS_ORIGINS: str = ""        # comma-separated exact browser origins
    TRANSCRIPT_KEY: str = ""      # Fernet key for encrypting transcripts
    TTS_VOICE: str = ""
    GENERATIVE_SPEECH: str = "off"  # D3: kill switch

@lru_cache
def get_settings() -> Settings:
    return Settings()
