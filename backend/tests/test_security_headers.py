"""Tests des en-t?tes HTTP de s?curit?."""

from app.config import settings


def test_security_headers_are_present(unauthenticated_client):
    """V?rifie les en-t?tes de s?curit? permanents."""

    response = unauthenticated_client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert (
        response.headers["Referrer-Policy"]
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers["Permissions-Policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


def test_hsts_is_absent_in_development(
    unauthenticated_client,
    monkeypatch,
):
    """HSTS ne doit pas ?tre envoy? en d?veloppement."""

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    response = unauthenticated_client.get("/health")

    assert "Strict-Transport-Security" not in response.headers


def test_hsts_is_present_in_production(
    unauthenticated_client,
    monkeypatch,
):
    """HSTS doit ?tre envoy? en production."""

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    response = unauthenticated_client.get("/health")

    assert (
        response.headers["Strict-Transport-Security"]
        == "max-age=31536000"
    )
