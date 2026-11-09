"""Tests de sécurité et d'authentification ClientPulse."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    hash_password,
)
from app.models.user import User


def create_test_user(test_db, is_active=True):
    """Insère un utilisateur de test dans la base SQLite isolée."""

    user = User(
        full_name="Utilisateur Test",
        email="auth.test@example.com",
        hashed_password=hash_password("TestPassword123!"),
        role="agent",
        is_active=is_active,
    )

    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    return user


def test_login_rejects_invalid_credentials(unauthenticated_client, test_db):
    """Une combinaison e-mail/mot de passe incorrecte doit être rejetée."""

    create_test_user(test_db)

    response = unauthenticated_client.post(
        "/api/auth/login",
        json={
            "email": "auth.test@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Adresse e-mail ou mot de passe incorrect."
    )


def test_login_rejects_inactive_user(unauthenticated_client, test_db):
    """Un compte désactivé ne doit pas pouvoir se connecter."""

    create_test_user(test_db, is_active=False)

    response = unauthenticated_client.post(
        "/api/auth/login",
        json={
            "email": "auth.test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Ce compte est désactivé."


def test_login_returns_access_token(unauthenticated_client, test_db):
    """Une connexion valide doit retourner un JWT Bearer."""

    create_test_user(test_db)

    response = unauthenticated_client.post(
        "/api/auth/login",
        json={
            "email": "auth.test@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"


def test_profile_accepts_valid_token(unauthenticated_client, test_db):
    """Un JWT valide doit permettre de consulter son profil."""

    user = create_test_user(test_db)
    token = create_access_token(str(user.id))

    response = unauthenticated_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "auth.test@example.com"
    assert response.json()["full_name"] == "Utilisateur Test"
    assert "hashed_password" not in response.json()


def test_profile_rejects_expired_token(unauthenticated_client, test_db):
    """Un JWT expiré doit être rejeté avec HTTP 401."""

    user = create_test_user(test_db)

    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = unauthenticated_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_profile_rejects_malformed_token(unauthenticated_client):
    """Un JWT malformé doit être rejeté avec HTTP 401."""

    response = unauthenticated_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401

def test_login_rate_limit_blocks_sixth_attempt(unauthenticated_client, test_db):
    """La sixi?me tentative de connexion doit ?tre limit?e."""

    create_test_user(test_db)

    responses = [
        unauthenticated_client.post(
            "/api/auth/login",
            json={
                "email": "auth.test@example.com",
                "password": "WrongPassword123!",
            },
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
