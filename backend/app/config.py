
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuration centralisée et sécurisée de ClientPulse."""

    APP_NAME: str = "ClientPulse API"
    APP_VERSION: str = "0.3.0"
    APP_DESCRIPTION: str = (
        "API de gestion des clients et des réclamations."
    )

    ENVIRONMENT: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    DEBUG: bool = True

    DATABASE_URL: str = Field(
        default=f"sqlite:///{BASE_DIR / 'clientpulse.db'}"
    )

    SECRET_KEY: str = Field(
        default="development-only-change-this-secret-key",
        min_length=32,
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)

    CORS_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        """Normalise le nom de l'environnement."""
        if not isinstance(value, str):
            raise ValueError("ENVIRONMENT doit être une chaîne.")

        return value.strip().lower()

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Valide et normalise les URL PostgreSQL et SQLite."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("DATABASE_URL ne peut pas être vide.")

        try:
            database_url = make_url(value.strip())
        except Exception as exc:
            raise ValueError(
                "DATABASE_URL n'est pas une URL SQLAlchemy valide."
            ) from exc

        driver = database_url.drivername

        # Les fournisseurs peuvent transmettre postgres:// ou
        # postgresql://. Le projet utilise psycopg version 3.
        if driver in {"postgres", "postgresql"}:
            database_url = database_url.set(
                drivername="postgresql+psycopg"
            )

        elif driver not in {
            "postgresql+psycopg",
            "sqlite",
            "sqlite+pysqlite",
        }:
            raise ValueError(
                "Pilote de base de données non pris en charge."
            )

        return database_url.render_as_string(hide_password=False)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Refuse les clés secrètes vides."""
        if not value or not value.strip():
            raise ValueError("SECRET_KEY ne peut pas être vide.")

        return value.strip()

    @property
    def database_url(self) -> str:
        """Retourne l'URL normalisée utilisée par SQLAlchemy et Alembic."""
        return self.DATABASE_URL

    @property
    def cors_origins(self) -> list[str]:
        """Valide et convertit les origines CORS en liste."""
        origins: list[str] = []

        for raw_origin in self.CORS_ORIGINS.split(","):
            origin = raw_origin.strip().rstrip("/")

            if not origin:
                continue

            try:
                parsed = urlsplit(origin)
                hostname = parsed.hostname
                # Accéder à port vérifie également sa validité.
                _ = parsed.port
            except ValueError as exc:
                raise ValueError(
                    f"Origine CORS invalide : {origin!r}."
                ) from exc

            if parsed.scheme not in {"http", "https"} or not hostname:
                raise ValueError(
                    f"Origine CORS invalide : {origin!r}."
                )

            if parsed.username is not None or parsed.password is not None:
                raise ValueError(
                    "Les origines CORS ne doivent pas contenir "
                    "d'identifiants."
                )

            if (
                "*" in parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    f"Une origine CORS doit contenir uniquement "
                    f"un schéma, un hôte et éventuellement un port : "
                    f"{origin!r}."
                )

            normalized_origin = f"{parsed.scheme}://{parsed.netloc}"

            if normalized_origin not in origins:
                origins.append(normalized_origin)

        return origins

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Applique les règles de sécurité en production."""

        # Valide la syntaxe CORS dans tous les environnements.
        origins = self.cors_origins

        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError(
                    "DEBUG doit être False en production."
                )

            normalized_key = self.SECRET_KEY.lower()

            weak_fragments = (
                "development-only",
                "change-me",
                "changeme",
                "change-this",
                "your-secret-key",
                "replace-me",
                "password",
                "example",
            )

            has_weak_fragment = any(
                fragment in normalized_key
                for fragment in weak_fragments
            )

            # Une cl? al?atoire doit pr?senter une diversit? suffisante.
            has_low_character_diversity = len(set(self.SECRET_KEY)) < 12

            # D?tecte les motifs cycliques simples : abc123abc123...
            has_repeated_pattern = any(
                len(self.SECRET_KEY) % size == 0
                and self.SECRET_KEY
                == self.SECRET_KEY[:size]
                * (len(self.SECRET_KEY) // size)
                for size in range(1, min(9, len(self.SECRET_KEY) // 2 + 1))
            )

            if (
                len(self.SECRET_KEY) < 32
                or has_weak_fragment
                or has_low_character_diversity
                or has_repeated_pattern
            ):
                raise ValueError(
                    "SECRET_KEY est trop faible ou pr?visible. "
                    "Utilisez une cl? al?atoire d'au moins 32 caract?res."
                )

            if make_url(self.DATABASE_URL).get_backend_name() != "postgresql":
                raise ValueError(
                    "PostgreSQL est obligatoire en production."
                )

            if not origins:
                raise ValueError(
                    "CORS_ORIGINS doit contenir au moins une origine."
                )

            if any(
                urlsplit(origin).scheme != "https"
                for origin in origins
            ):
                raise ValueError(
                    "Toutes les origines CORS doivent utiliser HTTPS "
                    "en production."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Retourne une configuration mise en cache."""
    return Settings()


settings = get_settings()
