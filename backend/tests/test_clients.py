
from fastapi.testclient import TestClient


def test_create_client(client: TestClient):
    """Un agent authentifié peut créer un client."""

    response = client.post(
        "/api/clients",
        json={
            "name": "Entreprise Test",
            "email": "entreprise@test.com",
            "company": "Test Company",
            "phone": "+21612345678",
            "status": "active",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Entreprise Test"
    assert data["email"] == "entreprise@test.com"
    assert data["status"] == "active"
    assert "id" in data


def test_list_clients(client: TestClient):
    """Un agent authentifié peut consulter la liste des clients."""

    create_response = client.post(
        "/api/clients",
        json={
            "name": "Client Liste",
            "email": "liste@test.com",
            "status": "active",
        },
    )

    assert create_response.status_code == 201

    response = client.get("/api/clients")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Client Liste"


def test_update_client(client: TestClient):
    """Un agent authentifié peut modifier un client."""

    create_response = client.post(
        "/api/clients",
        json={
            "name": "Client Initial",
            "email": "initial@test.com",
            "status": "active",
        },
    )

    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = client.patch(
        f"/api/clients/{client_id}",
        json={
            "company": "Nouvelle Entreprise",
            "status": "prospect",
        },
    )

    assert response.status_code == 200
    assert response.json()["company"] == "Nouvelle Entreprise"
    assert response.json()["status"] == "prospect"


def test_delete_client(admin_client: TestClient):
    """Seul un administrateur peut supprimer un client."""

    create_response = admin_client.post(
        "/api/clients",
        json={
            "name": "Client à supprimer",
            "email": "delete@test.com",
            "status": "active",
        },
    )

    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = admin_client.delete(f"/api/clients/{client_id}")

    assert response.status_code == 204

    get_response = admin_client.get(f"/api/clients/{client_id}")
    assert get_response.status_code == 404


def test_agent_cannot_delete_client(client: TestClient):
    """Un agent ne peut pas supprimer un client."""

    create_response = client.post(
        "/api/clients",
        json={
            "name": "Client protégé",
            "email": "protected@test.com",
            "status": "active",
        },
    )

    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = client.delete(f"/api/clients/{client_id}")

    assert response.status_code == 403

    # Le client doit toujours exister.
    get_response = client.get(f"/api/clients/{client_id}")
    assert get_response.status_code == 200


def test_duplicate_email(client: TestClient):
    """Une adresse e-mail déjà utilisée doit être refusée."""

    payload = {
        "name": "Client Test",
        "email": "duplicate@test.com",
        "status": "active",
    }

    first_response = client.post("/api/clients", json=payload)
    second_response = client.post("/api/clients", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_unauthenticated_user_cannot_list_clients(
    unauthenticated_client: TestClient,
):
    """Un utilisateur sans token ne peut pas consulter les clients."""

    response = unauthenticated_client.get("/api/clients")

    assert response.status_code == 401
