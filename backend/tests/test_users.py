import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.models.user import User
from app.routers.users import ensure_last_admin_protection
from app.services import file_storage
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models.user import User
from app.routers.users import ensure_last_admin_protection


def create_agent(
    admin_client: TestClient,
    email: str = "agent.test@example.com",
    full_name: str = "Agent Test",
) -> dict:
    """Crée un agent avec un nom et un e-mail personnalisables."""

    response = admin_client.post(
        "/api/users/",
        json={
            "full_name": full_name,
            "email": email,
            "password": "AgentPassword123!",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()



def create_test_client(api_client: TestClient) -> int:
    """Crée un client CRM et retourne son identifiant."""

    response = api_client.post(
        "/api/clients",
        json={
            "name": "Client Test Utilisateur",
            "email": "client-user-test@example.com",
            "company": "Test Company",
            "phone": "+21612345678",
            "status": "active",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_test_ticket(
    api_client: TestClient,
    client_id: int,
    assigned_to: str = "Agent Test",
) -> dict:
    """Crée un ticket affecté à un agent."""

    response = api_client.post(
        "/api/tickets",
        json={
            "title": "Ticket de test utilisateur",
            "description": "Ticket créé pour vérifier les affectations.",
            "priority": "medium",
            "status": "open",
            "client_id": client_id,
            "assigned_to": assigned_to,
        },
    )

    # Vérifie que le ticket a bien été créé.
    assert response.status_code == 201, response.text

    # Retourne les données du ticket créé.
    return response.json()# ---------------------------------------------------------------------
# OUTILS DE TEST POUR LES AVATARS ADMINISTRATIFS
# ---------------------------------------------------------------------


@pytest.fixture()
def isolated_user_avatar_storage(tmp_path, monkeypatch):
    """Isole le stockage des avatars administratifs."""

    monkeypatch.setattr(
        file_storage.settings,
        "STORAGE_DIR",
        tmp_path,
    )

    return tmp_path


def make_user_avatar(color: str = "blue") -> bytes:
    """Génère une image PNG valide en mémoire."""

    buffer = io.BytesIO()

    image = Image.new("RGB", (32, 32), color)
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def get_stored_user_avatars(storage_dir):
    """Retourne les avatars réellement présents sur le disque."""

    avatar_dir = storage_dir / "avatars"

    if not avatar_dir.exists():
        return []

    return list(avatar_dir.iterdir())

    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------
# CONSULTATION DES UTILISATEURS
# ---------------------------------------------------------------------


def test_admin_can_list_users(admin_client: TestClient):
    """Un administrateur peut consulter la liste des utilisateurs."""

    response = admin_client.get("/api/users/")

    assert response.status_code == 200

    users = response.json()

    assert len(users) == 1
    assert users[0]["email"] == "admin@clientpulse.com"
    assert users[0]["role"] == "admin"
    assert "hashed_password" not in users[0]
    assert "password" not in users[0]


def test_admin_can_get_user(admin_client: TestClient):
    """Un administrateur peut consulter un utilisateur par son ID."""

    agent = create_agent(admin_client)

    response = admin_client.get(f"/api/users/{agent['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == agent["id"]


def test_admin_get_unknown_user_returns_404(admin_client: TestClient):
    """Un identifiant inexistant doit retourner 404."""

    response = admin_client.get("/api/users/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------
# CRÉATION DES UTILISATEURS
# ---------------------------------------------------------------------


def test_admin_can_create_agent(admin_client: TestClient):
    """Un administrateur peut créer un compte agent."""

    agent = create_agent(admin_client)

    assert agent["full_name"] == "Agent Test"
    assert agent["email"] == "agent.test@example.com"
    assert agent["role"] == "agent"
    assert agent["is_active"] is True
    assert "hashed_password" not in agent
    assert "password" not in agent


def test_admin_cannot_create_duplicate_email(admin_client: TestClient):
    """Une adresse e-mail déjà utilisée doit être refusée."""

    create_agent(admin_client)

    response = admin_client.post(
        "/api/users/",
        json={
            "full_name": "Autre Agent",
            "email": "agent.test@example.com",
            "password": "AnotherPassword123!",
        },
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------
# MODIFICATION DES UTILISATEURS
# ---------------------------------------------------------------------


def test_admin_can_update_user(admin_client: TestClient):
    """Un administrateur peut modifier le nom et l'e-mail d'un agent."""

    agent = create_agent(admin_client)

    response = admin_client.patch(
        f"/api/users/{agent['id']}",
        json={
            "full_name": "Agent Modifie",
            "email": "agent.modifie@example.com",
        },
    )

    assert response.status_code == 200, response.text

    updated_agent = response.json()

    assert updated_agent["id"] == agent["id"]
    assert updated_agent["full_name"] == "Agent Modifie"
    assert updated_agent["email"] == "agent.modifie@example.com"
    assert updated_agent["role"] == "agent"


def test_admin_can_update_only_user_name(admin_client: TestClient):
    """La modification du nom seul conserve l'adresse e-mail."""

    agent = create_agent(admin_client)

    response = admin_client.patch(
        f"/api/users/{agent['id']}",
        json={"full_name": "Nouveau Nom"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Nouveau Nom"
    assert response.json()["email"] == agent["email"]


def test_admin_can_update_only_user_email(admin_client: TestClient):
    """La modification de l'e-mail seul conserve le nom."""

    agent = create_agent(admin_client)

    response = admin_client.patch(
        f"/api/users/{agent['id']}",
        json={"email": "nouveau.email@example.com"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == agent["full_name"]
    assert response.json()["email"] == "nouveau.email@example.com"


def test_admin_cannot_update_user_with_duplicate_email(
    admin_client: TestClient,
):
    """Un e-mail déjà utilisé ne peut pas être attribué."""

    first_agent = create_agent(admin_client)

    second_agent = create_agent(
        admin_client,
        email="second.agent@example.com",
        full_name="Second Agent",
    )

    response = admin_client.patch(
        f"/api/users/{second_agent['id']}",
        json={"email": first_agent["email"]},
    )

    assert response.status_code == 409


def test_admin_cannot_update_user_with_duplicate_name(
    admin_client: TestClient,
):
    """Un nom déjà utilisé ne peut pas être attribué."""

    first_agent = create_agent(admin_client)

    second_agent = create_agent(
        admin_client,
        email="second.agent@example.com",
        full_name="Second Agent",
    )

    response = admin_client.patch(
        f"/api/users/{second_agent['id']}",
        json={"full_name": first_agent["full_name"]},
    )

    assert response.status_code == 409


def test_admin_cannot_update_unknown_user(admin_client: TestClient):
    """La modification d'un utilisateur inexistant renvoie 404."""

    response = admin_client.patch(
        "/api/users/9999",
        json={"full_name": "Nom Inconnu"},
    )

    assert response.status_code == 404


def test_admin_cannot_update_user_with_empty_payload(
    admin_client: TestClient,
):
    """Une modification sans champ doit être refusée."""

    agent = create_agent(admin_client)

    response = admin_client.patch(
        f"/api/users/{agent['id']}",
        json={},
    )

    assert response.status_code == 422


def test_admin_can_rename_user_and_update_ticket_assignment(
    admin_client: TestClient,
):
    """Le renommage d'un agent actualise ses tickets."""

    agent = create_agent(admin_client)

    client_id = create_test_client(admin_client)

    ticket = create_test_ticket(
        admin_client,
        client_id,
        assigned_to=agent["full_name"],
    )

    response = admin_client.patch(
        f"/api/users/{agent['id']}",
        json={"full_name": "Agent Renomme"},
    )

    assert response.status_code == 200, response.text

    ticket_response = admin_client.get(
        f"/api/tickets/{ticket['id']}"
    )

    assert ticket_response.status_code == 200
    assert ticket_response.json()["assigned_to"] == "Agent Renomme"


# ---------------------------------------------------------------------
# ACTIVATION ET DÉSACTIVATION
# ---------------------------------------------------------------------


def test_admin_can_deactivate_user(admin_client: TestClient):
    """Un administrateur peut désactiver un agent."""

    agent = create_agent(admin_client)

    response = admin_client.patch(
        f"/api/users/{agent['id']}/status",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_can_reactivate_user(admin_client: TestClient):
    """Un administrateur peut réactiver un agent."""

    agent = create_agent(admin_client)

    admin_client.patch(
        f"/api/users/{agent['id']}/status",
        json={"is_active": False},
    )

    response = admin_client.patch(
        f"/api/users/{agent['id']}/status",
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


# ---------------------------------------------------------------------
# SUPPRESSION DES UTILISATEURS
# ---------------------------------------------------------------------


def test_admin_can_delete_user_without_tickets(admin_client: TestClient):
    """Un administrateur peut supprimer un agent sans tickets."""

    agent = create_agent(admin_client)

    response = admin_client.delete(
        f"/api/users/{agent['id']}"
    )

    assert response.status_code == 204

    check = admin_client.get(f"/api/users/{agent['id']}")
    assert check.status_code == 404


def test_admin_cannot_delete_own_account(admin_client: TestClient):
    """Un administrateur ne peut pas supprimer son propre compte."""

    current_user = admin_client.get("/api/auth/me").json()

    response = admin_client.delete(
        f"/api/users/{current_user['id']}"
    )

    assert response.status_code == 400


def test_admin_cannot_delete_user_with_tickets_without_replacement(
    admin_client: TestClient,
):
    """La suppression avec tickets exige un agent de remplacement."""

    agent = create_agent(admin_client)

    client_id = create_test_client(admin_client)

    create_test_ticket(
        admin_client,
        client_id,
        assigned_to=agent["full_name"],
    )

    response = admin_client.delete(
        f"/api/users/{agent['id']}"
    )

    assert response.status_code == 409
    assert response.json()["detail"]["requires_replacement"] is True
    assert response.json()["detail"]["ticket_count"] == 1


def test_admin_can_delete_user_and_reassign_tickets(
    admin_client: TestClient,
):
    """Les tickets sont réaffectés avant la suppression du compte."""

    agent_to_delete = create_agent(
        admin_client,
        email="agent.delete@example.com",
        full_name="Agent A Supprimer",
    )

    replacement_agent = create_agent(
        admin_client,
        email="agent.replacement@example.com",
        full_name="Agent Remplacement",
    )

    client_id = create_test_client(admin_client)

    ticket = create_test_ticket(
        admin_client,
        client_id,
        assigned_to=agent_to_delete["full_name"],
    )

    response = admin_client.delete(
        f"/api/users/{agent_to_delete['id']}",
        params={"replacement_user_id": replacement_agent["id"]},
    )

    assert response.status_code == 204

    check_user = admin_client.get(
        f"/api/users/{agent_to_delete['id']}"
    )
    assert check_user.status_code == 404

    check_ticket = admin_client.get(
        f"/api/tickets/{ticket['id']}"
    )

    assert check_ticket.status_code == 200
    assert (
        check_ticket.json()["assigned_to"]
        == replacement_agent["full_name"]
    )


def test_admin_cannot_delete_user_with_inactive_replacement(
    admin_client: TestClient,
):
    """Un agent inactif ne peut pas être choisi comme remplaçant."""

    agent_to_delete = create_agent(
        admin_client,
        email="agent.delete@example.com",
        full_name="Agent A Supprimer",
    )

    inactive_agent = create_agent(
        admin_client,
        email="agent.inactive@example.com",
        full_name="Agent Inactif",
    )

    client_id = create_test_client(admin_client)

    create_test_ticket(
        admin_client,
        client_id,
        assigned_to=agent_to_delete["full_name"],
    )

    admin_client.patch(
        f"/api/users/{inactive_agent['id']}/status",
        json={"is_active": False},
    )

    response = admin_client.delete(
        f"/api/users/{agent_to_delete['id']}",
        params={"replacement_user_id": inactive_agent["id"]},
    )

    assert response.status_code == 422


def test_admin_cannot_delete_unknown_user(admin_client: TestClient):
    """La suppression d'un utilisateur inexistant renvoie 404."""

    response = admin_client.delete("/api/users/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------
# AUTORISATIONS
# ---------------------------------------------------------------------


def test_agent_cannot_manage_users(client: TestClient):
    """Un agent ne peut pas consulter les utilisateurs."""

    response = client.get("/api/users/")

    assert response.status_code == 403


def test_agent_cannot_create_another_agent(client: TestClient):
    """Un agent ne peut pas créer un autre compte."""

    response = client.post(
        "/api/users/",
        json={
            "full_name": "Agent Interdit",
            "email": "forbidden@example.com",
            "password": "AgentPassword123!",
        },
    )

    assert response.status_code == 403


def test_agent_cannot_update_users(client: TestClient):
    """Un agent ne peut pas modifier les utilisateurs."""

    response = client.patch(
        "/api/users/1",
        json={"full_name": "Nom Interdit"},
    )

    assert response.status_code == 403


def test_agent_cannot_delete_users(client: TestClient):
    """Un agent ne peut pas supprimer les utilisateurs."""

    response = client.delete("/api/users/1")

    assert response.status_code == 403


def test_unauthenticated_user_cannot_create_agent(
    unauthenticated_client: TestClient,
):
    """Un utilisateur non connecté ne peut pas créer un agent."""

    response = unauthenticated_client.post(
        "/api/users/",
        json={
            "full_name": "Agent Interdit",
            "email": "unauthenticated@example.com",
            "password": "AgentPassword123!",
        },
    )

    assert response.status_code == 401


def test_unauthenticated_user_cannot_update_user(
    unauthenticated_client: TestClient,
):
    """Un utilisateur non connecté ne peut pas modifier un compte."""

    response = unauthenticated_client.patch(
        "/api/users/1",
        json={"full_name": "Nom Interdit"},
    )

    assert response.status_code == 401


def test_unauthenticated_user_cannot_delete_user(
    unauthenticated_client: TestClient,
):
    """Un utilisateur non connecté ne peut pas supprimer un compte."""

    response = unauthenticated_client.delete("/api/users/1")

    assert response.status_code == 401


def test_public_registration_is_disabled(
    unauthenticated_client: TestClient,
):
    """L'ancienne inscription publique n'est plus disponible."""

    response = unauthenticated_client.post(
        "/api/auth/register",
        json={
            "full_name": "Agent Public",
            "email": "public@example.com",
            "password": "AgentPassword123!",
        },
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("operation", "expected_detail"),
    [
        (
            "supprimer",
            "Impossible de supprimer le dernier administrateur actif.",
        ),
        (
            "désactiver",
            "Impossible de désactiver le dernier administrateur actif.",
        ),
    ],
)
def test_last_active_admin_protection_blocks_last_admin(
    test_db,
    operation,
    expected_detail,
):
    """Bloque la suppression et la désactivation du dernier administrateur."""

    admin = User(
        full_name="Unique Admin",
        email="unique.admin@example.com",
        hashed_password="test-hash",
        role="admin",
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)

    with pytest.raises(HTTPException) as exc_info:
        ensure_last_admin_protection(admin, test_db, operation=operation)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == expected_detail


def test_last_admin_protection_allows_operation_with_two_active_admins(test_db):
    """Autorise l'opération lorsqu'un autre administrateur actif existe."""

    first_admin = User(
        full_name="First Admin",
        email="first.admin@example.com",
        hashed_password="test-hash",
        role="admin",
        is_active=True,
    )
    second_admin = User(
        full_name="Second Admin",
        email="second.admin@example.com",
        hashed_password="test-hash",
        role="admin",
        is_active=True,
    )

    test_db.add_all([first_admin, second_admin])
    test_db.commit()
    test_db.refresh(first_admin)

    ensure_last_admin_protection(first_admin, test_db, operation="supprimer")
    ensure_last_admin_protection(first_admin, test_db, operation="désactiver")

# ---------------------------------------------------------------------
# RÉINITIALISATION DES MOTS DE PASSE
# ---------------------------------------------------------------------


def test_admin_can_reset_user_password_and_invalidate_old_token(
    admin_client: TestClient,
    test_db,
):
    """Vérifie la réinitialisation sécurisée du mot de passe d'un agent."""

    from fastapi.testclient import TestClient as HTTPTestClient

    from app.core.security import create_access_token, verify_password
    from app.main import app

    # Crée un agent via l'API d'administration.
    agent = create_agent(admin_client)

    # Récupère son compte dans la base de test.
    user = test_db.query(User).filter(User.id == agent["id"]).first()
    assert user is not None

    # Génère un ancien JWT avant la réinitialisation.
    old_token = create_access_token(
        str(user.id),
        token_version=user.token_version,
    )

    # Réinitialise le mot de passe depuis le compte administrateur.
    response = admin_client.post(
        f"/api/users/{user.id}/password/reset"
    )

    assert response.status_code == 200, response.text

    temporary_password = response.json()["temporary_password"]

    # Vérifie les caractéristiques du mot de passe temporaire.
    assert len(temporary_password) == 24
    assert any(char.islower() for char in temporary_password)
    assert any(char.isupper() for char in temporary_password)
    assert any(char.isdigit() for char in temporary_password)

    # Recharge le compte pour vérifier les changements persistés.
    test_db.refresh(user)

    assert verify_password(temporary_password, user.hashed_password)
    assert user.must_change_password is True
    assert user.password_changed_at is None
    assert user.token_version == 1

    # Vérifie que l'ancien JWT est désormais refusé.
    with HTTPTestClient(
        app,
        headers={"Authorization": f"Bearer {old_token}"},
    ) as old_session:
        old_token_response = old_session.get("/api/auth/me")

    assert old_token_response.status_code == 401


def test_agent_cannot_reset_user_password(client: TestClient):
    """Un agent ne peut pas réinitialiser le mot de passe d'un utilisateur."""

    response = client.post("/api/users/1/password/reset")

    assert response.status_code == 403

# ---------------------------------------------------------------------
# GESTION ADMINISTRATIVE DES AVATARS
# ---------------------------------------------------------------------


def test_admin_can_upload_user_avatar(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Un administrateur peut ajouter un avatar à un agent."""

    agent = create_agent(admin_client)

    response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["id"] == agent["id"]
    assert payload["avatar_url"] == (
        f"/api/auth/users/{agent['id']}/avatar"
    )
    assert "avatar_path" not in payload

    stored_files = get_stored_user_avatars(
        isolated_user_avatar_storage
    )

    assert len(stored_files) == 1

    # Vérifie que l'avatar est accessible via son URL authentifiée.
    avatar_response = admin_client.get(payload["avatar_url"])

    assert avatar_response.status_code == 200
    assert avatar_response.headers["content-type"] == "image/png"


def test_admin_can_replace_user_avatar(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Le remplacement supprime l'ancien fichier physique."""

    agent = create_agent(admin_client)

    first_response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "first.png",
                make_user_avatar("blue"),
                "image/png",
            )
        },
    )

    assert first_response.status_code == 200

    old_files = get_stored_user_avatars(
        isolated_user_avatar_storage
    )

    assert len(old_files) == 1
    old_file = old_files[0]

    second_response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "second.png",
                make_user_avatar("red"),
                "image/png",
            )
        },
    )

    assert second_response.status_code == 200

    new_files = get_stored_user_avatars(
        isolated_user_avatar_storage
    )

    assert len(new_files) == 1
    assert new_files[0] != old_file
    assert not old_file.exists()

    assert (
        second_response.json()["avatar_url"]
        == first_response.json()["avatar_url"]
    )


def test_admin_can_delete_user_avatar(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Un administrateur peut supprimer l'avatar d'un agent."""

    agent = create_agent(admin_client)

    upload_response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    assert upload_response.status_code == 200

    avatar_url = upload_response.json()["avatar_url"]

    assert len(
        get_stored_user_avatars(isolated_user_avatar_storage)
    ) == 1

    response = admin_client.delete(
        f"/api/users/{agent['id']}/avatar"
    )

    assert response.status_code == 204
    assert response.content == b""

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []

    # L'URL de l'avatar supprimé ne doit plus être accessible.
    avatar_response = admin_client.get(avatar_url)

    assert avatar_response.status_code == 404


def test_admin_can_delete_user_avatar_idempotently(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Supprimer un avatar absent ne provoque pas d'erreur."""

    agent = create_agent(admin_client)

    first_response = admin_client.delete(
        f"/api/users/{agent['id']}/avatar"
    )

    second_response = admin_client.delete(
        f"/api/users/{agent['id']}/avatar"
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 204

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []


def test_admin_cannot_upload_invalid_user_avatar(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Un fichier qui n'est pas une image est refusé."""

    agent = create_agent(admin_client)

    response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "fake.png",
                b"This is not a valid image.",
                "image/png",
            )
        },
    )

    assert response.status_code == 400

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []


def test_admin_cannot_upload_avatar_to_unknown_user(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """Un utilisateur inexistant renvoie 404."""

    response = admin_client.put(
        "/api/users/9999/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    assert response.status_code == 404

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []


def test_agent_cannot_manage_user_avatars(
    client: TestClient,
    isolated_user_avatar_storage,
):
    """Un agent ne peut ni ajouter ni supprimer un avatar administratif."""

    profile = client.get("/api/auth/me")

    assert profile.status_code == 200

    user_id = profile.json()["id"]

    upload_response = client.put(
        f"/api/users/{user_id}/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    delete_response = client.delete(
        f"/api/users/{user_id}/avatar"
    )

    assert upload_response.status_code == 403
    assert delete_response.status_code == 403

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []


def test_unauthenticated_user_cannot_manage_user_avatars(
    unauthenticated_client: TestClient,
    isolated_user_avatar_storage,
):
    """Les routes administratives exigent une authentification."""

    upload_response = unauthenticated_client.put(
        "/api/users/1/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    delete_response = unauthenticated_client.delete(
        "/api/users/1/avatar"
    )

    assert upload_response.status_code == 401
    assert delete_response.status_code == 401

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []


def test_deleting_user_also_deletes_physical_avatar(
    admin_client: TestClient,
    isolated_user_avatar_storage,
):
    """La suppression du compte supprime aussi son avatar physique."""

    agent = create_agent(admin_client)

    upload_response = admin_client.put(
        f"/api/users/{agent['id']}/avatar",
        files={
            "file": (
                "avatar.png",
                make_user_avatar(),
                "image/png",
            )
        },
    )

    assert upload_response.status_code == 200

    stored_files = get_stored_user_avatars(
        isolated_user_avatar_storage
    )

    assert len(stored_files) == 1

    avatar_file = stored_files[0]

    response = admin_client.delete(
        f"/api/users/{agent['id']}"
    )

    assert response.status_code == 204

    assert not avatar_file.exists()

    assert get_stored_user_avatars(
        isolated_user_avatar_storage
    ) == []

    check_user = admin_client.get(
        f"/api/users/{agent['id']}"
    )

    assert check_user.status_code == 404
