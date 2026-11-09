"""Tests de validation de la configuration ClientPulse."""

import secrets

import pytest
from pydantic import ValidationError

from app.config import BASE_DIR, Settings


def make_settings(**overrides) -> Settings:
    """Construit une configuration isol?e des variables locales."""

    values = {
        "ENVIRONMENT": "development",
        "DEBUG": True,
        "SECRET_KEY": "test-secret-key-for-clientpulse-123456",
        "DATABASE_URL": f"sqlite:///{BASE_DIR / 'test_clientpulse.db'}",
        "CORS_ORIGINS": (
            "http://localhost:5173,"
            "http://127.0.0.1:5173"
        ),
    }
    values.update(overrides)

    return Settings(_env_file=None, **values)


def test_sqlite_configuration_is_preserved():
    """SQLite doit rester utilisable en d?veloppement."""

    settings = make_settings()

    assert settings.ENVIRONMENT == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@pytest.mark.parametrize(
    "database_url",
    [
        "postgres://user:password@localhost:5432/clientpulse",
        "postgresql://user:password@localhost:5432/clientpulse",
    ],
)
def test_postgresql_urls_are_normalized(database_url):
    """Les URL PostgreSQL classiques doivent utiliser psycopg 3."""

    settings = make_settings(DATABASE_URL=database_url)

    assert settings.database_url.startswith(
        "postgresql+psycopg://"
    )


def test_psycopg_driver_is_preserved():
    """Une URL d?j? normalis?e ne doit pas ?tre modifi?e."""

    url = "postgresql+psycopg://user:password@localhost:5432/clientpulse"

    settings = make_settings(DATABASE_URL=url)

    assert settings.database_url == url


def test_unsupported_database_driver_is_rejected():
    """Un pilote non pris en charge doit provoquer une erreur."""

    with pytest.raises(ValidationError):
        make_settings(
            DATABASE_URL="mysql://user:password@localhost/clientpulse"
        )


def test_malformed_database_url_is_rejected():
    """Une URL de base de donn?es sans pilote valide doit ?tre refus?e."""

    with pytest.raises(ValidationError):
        make_settings(DATABASE_URL="not-a-url")


@pytest.mark.parametrize(
    "cors_origins",
    [
        "https://example.com/path",
        "https://example.com?query=1",
        "https://user:password@example.com",
        "https://example.com,invalid-origin",
        "https://*.example.com",
        "https://example.com:99999",
    ],
)
def test_invalid_cors_origins_are_rejected(cors_origins):
    """Les origines CORS doivent ?tre des origines valides."""

    with pytest.raises(ValidationError):
        make_settings(CORS_ORIGINS=cors_origins)


def test_duplicate_cors_origins_are_removed():
    """Les origines r?p?t?es ne doivent appara?tre qu'une fois."""

    settings = make_settings(
        CORS_ORIGINS=(
            "https://example.com,"
            "https://example.com/"
        )
    )

    assert settings.cors_origins == ["https://example.com"]


def test_production_rejects_debug_mode():
    """DEBUG doit ?tre d?sactiv? en production."""

    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            DEBUG=True,
            DATABASE_URL=(
                "postgresql+psycopg://user:password@localhost:5432/clientpulse"
            ),
            CORS_ORIGINS="https://example.com",
        )


def test_production_rejects_sqlite():
    """SQLite ne doit pas ?tre utilis? en production."""

    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DATABASE_URL="sqlite:///clientpulse.db",
            CORS_ORIGINS="https://example.com",
        )


def test_production_rejects_http_cors():
    """Les origines de production doivent utiliser HTTPS."""

    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DATABASE_URL=(
                "postgresql+psycopg://user:password@localhost:5432/clientpulse"
            ),
            CORS_ORIGINS="http://example.com",
        )


def test_valid_production_configuration():
    """Une configuration PostgreSQL s?curis?e doit ?tre accept?e."""

    settings = make_settings(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY=secrets.token_urlsafe(48),
        DATABASE_URL=(
            "postgresql+psycopg://user:password@localhost:5432/clientpulse"
        ),
        CORS_ORIGINS="https://clientpulse.example.com",
    )

    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.cors_origins == [
        "https://clientpulse.example.com"
    ]


@pytest.mark.parametrize(
    "secret_key",
    [
        "a" * 64,
        "abc123" * 11,
        "development-only-change-this-secret-key",
        "your-secret-key-change-this-before-deploying-123456",
    ],
)
def test_production_rejects_weak_secret_keys(secret_key):
    """Les cl?s longues mais pr?visibles doivent ?tre refus?es."""

    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY=secret_key,
            DATABASE_URL=(
                "postgresql+psycopg://user:password@localhost:5432/clientpulse"
            ),
            CORS_ORIGINS="https://clientpulse.example.com",
        )


@pytest.mark.parametrize(
    "environment",
    ["prod", "staging", "", None, 123],
)
def test_invalid_environment_is_rejected(environment):
    """Un environnement inconnu doit ?tre refus?."""

    with pytest.raises(ValidationError):
        make_settings(ENVIRONMENT=environment)


def test_environment_is_normalized():
    """L'environnement doit ?tre normalis? en minuscules."""

    settings = make_settings(ENVIRONMENT=" DEVELOPMENT ")

    assert settings.ENVIRONMENT == "development"


@pytest.mark.parametrize(
    "secret_key",
    ["", " " * 40, "a" * 31],
)
def test_invalid_secret_keys_are_rejected(secret_key):
    """Une cl? vide, compos?e d'espaces ou trop courte est refus?e."""

    with pytest.raises(ValidationError):
        make_settings(SECRET_KEY=secret_key)


@pytest.mark.parametrize(
    "expiration",
    [0, -1],
)
def test_invalid_jwt_expiration_is_rejected(expiration):
    """La dur?e de validit? du JWT doit ?tre strictement positive."""

    with pytest.raises(ValidationError):
        make_settings(ACCESS_TOKEN_EXPIRE_MINUTES=expiration)


def test_production_rejects_empty_cors_origins():
    """La production doit avoir au moins une origine CORS."""

    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DATABASE_URL=(
                "postgresql+psycopg://user:password@localhost:5432/clientpulse"
            ),
            CORS_ORIGINS="",
        )
