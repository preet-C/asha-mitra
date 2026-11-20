# ASHA Mitra — config loader
# Reads all settings from backend/.env via pydantic-settings.
# Never import this in frontend. Never print SECRET values.

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    GNANI_API_KEY: str = ""
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    DATABASE_URL: str = ""        # empty = in-memory repo
    TRANSCRIPT_KEY: str = ""      # Fernet key for encrypting transcripts
    TTS_VOICE: str = ""
    GENERATIVE_SPEECH: str = "off"  # D3: kill switch

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
