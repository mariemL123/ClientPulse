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

def test_change_password_success_and_token_rotation(
    unauthenticated_client,
    test_db,
):
    """Le changement de mot de passe renouvelle le JWT et invalide l'ancien."""

    user = create_test_user(test_db)
    old_token = create_access_token(
        str(user.id),
        token_version=user.token_version,
    )

    response = unauthenticated_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={
            "current_password": "TestPassword123!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!",
        },
    )

    assert response.status_code == 200, response.text

    new_token = response.json()["access_token"]
    assert new_token
    assert new_token != old_token

    test_db.refresh(user)

    assert user.must_change_password is False
    assert user.token_version == 1
    assert user.password_changed_at is not None

    # Le nouveau JWT doit être accepté.
    new_response = unauthenticated_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert new_response.status_code == 200

    # L'ancien JWT doit être invalidé.
    old_response = unauthenticated_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert old_response.status_code == 401


def test_change_password_rejects_wrong_current_password(
    unauthenticated_client,
    test_db,
):
    """Un mot de passe actuel incorrect doit être rejeté."""

    user = create_test_user(test_db)
    token = create_access_token(str(user.id))

    response = unauthenticated_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Le mot de passe actuel est incorrect."
    )

    test_db.refresh(user)
    assert user.token_version == 0


def test_change_password_rejects_mismatched_confirmation(
    unauthenticated_client,
    test_db,
):
    """Deux nouveaux mots de passe différents doivent être rejetés."""

    user = create_test_user(test_db)
    token = create_access_token(str(user.id))

    response = unauthenticated_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "TestPassword123!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "DifferentPassword789!",
        },
    )

    assert response.status_code == 422


def test_change_password_rejects_same_password(
    unauthenticated_client,
    test_db,
):
    """Le nouveau mot de passe doit être différent de l'ancien."""

    user = create_test_user(test_db)
    token = create_access_token(str(user.id))

    response = unauthenticated_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "TestPassword123!",
            "new_password": "TestPassword123!",
            "confirm_password": "TestPassword123!",
        },
    )

    assert response.status_code == 422

    test_db.refresh(user)
    assert user.token_version == 0
