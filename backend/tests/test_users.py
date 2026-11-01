
from fastapi.testclient import TestClient


def test_admin_can_list_users(admin_client: TestClient):
    """Un administrateur peut consulter la liste des utilisateurs."""

    response = admin_client.get("/api/users/")

    assert response.status_code == 200

    users = response.json()
    assert len(users) == 1
    assert users[0]["email"] == "admin@clientpulse.com"
    assert users[0]["role"] == "admin"

    # Vérifie qu'aucun mot de passe n'est exposé.
    assert "hashed_password" not in users[0]
    assert "password" not in users[0]


def test_admin_can_get_user(admin_client: TestClient):
    """Un administrateur peut consulter un utilisateur par son ID."""

    list_response = admin_client.get("/api/users/")
    user_id = list_response.json()[0]["id"]

    response = admin_client.get(f"/api/users/{user_id}")

    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_admin_get_unknown_user_returns_404(admin_client: TestClient):
    """Un identifiant inexistant doit retourner 404."""

    response = admin_client.get("/api/users/9999")

    assert response.status_code == 404


def test_admin_can_deactivate_user(admin_client: TestClient):
    """Un administrateur peut désactiver un autre compte."""

    # Création d'un compte agent.
    register_response = admin_client.post(
        "/api/auth/register",
        json={
            "full_name": "Agent Test",
            "email": "agent.status@example.com",
            "password": "AgentPassword123!",
        },
    )

    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    response = admin_client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_can_reactivate_user(admin_client: TestClient):
    """Un administrateur peut réactiver un compte désactivé."""

    register_response = admin_client.post(
        "/api/auth/register",
        json={
            "full_name": "Agent Reactivation",
            "email": "agent.reactivate@example.com",
            "password": "AgentPassword123!",
        },
    )

    user_id = register_response.json()["id"]

    admin_client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": False},
    )

    response = admin_client.patch(
        f"/api/users/{user_id}/status",
        json={"is_active": True},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_admin_cannot_deactivate_own_account(admin_client: TestClient):
    """Un administrateur ne peut pas désactiver son propre compte."""

    users_response = admin_client.get("/api/users/")
    admin_id = users_response.json()[0]["id"]

    response = admin_client.patch(
        f"/api/users/{admin_id}/status",
        json={"is_active": False},
    )

    assert response.status_code == 400


def test_agent_cannot_manage_users(client: TestClient):
    """Un agent ne peut pas accéder à l'administration des utilisateurs."""

    response = client.get("/api/users/")

    assert response.status_code == 403


def test_unauthenticated_user_cannot_manage_users(
    unauthenticated_client: TestClient,
):
    """Un utilisateur sans token ne peut pas gérer les comptes."""

    response = unauthenticated_client.get("/api/users/")

    assert response.status_code == 401
