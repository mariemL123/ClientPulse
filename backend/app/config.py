
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuration centralisée de ClientPulse."""

    APP_NAME: str = "ClientPulse API"
    APP_VERSION: str = "0.3.0"
    APP_DESCRIPTION: str = (
        "API de gestion des clients et des réclamations."
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = Field(
        default=f"sqlite:///{BASE_DIR / 'clientpulse.db'}"
    )

    SECRET_KEY: str = Field(
        default="development-only-change-this-secret-key"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retourne une configuration mise en cache."""

    return Settings()


settings = get_settings()
