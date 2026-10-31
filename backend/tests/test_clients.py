
from fastapi.testclient import TestClient


def test_create_client(client: TestClient):
    """Vérifie la création d'un client."""

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
    """Vérifie que la liste retourne les clients créés."""

    client.post(
        "/api/clients",
        json={
            "name": "Client Liste",
            "email": "liste@test.com",
            "status": "active",
        },
    )

    response = client.get("/api/clients")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Client Liste"


def test_update_client(client: TestClient):
    """Vérifie la modification d'un client."""

    create_response = client.post(
        "/api/clients",
        json={
            "name": "Client Initial",
            "email": "initial@test.com",
            "status": "active",
        },
    )

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


def test_delete_client(client: TestClient):
    """Vérifie la suppression d'un client."""

    create_response = client.post(
        "/api/clients",
        json={
            "name": "Client à supprimer",
            "email": "delete@test.com",
            "status": "active",
        },
    )

    client_id = create_response.json()["id"]

    response = client.delete(f"/api/clients/{client_id}")

    assert response.status_code == 204

    get_response = client.get(f"/api/clients/{client_id}")
    assert get_response.status_code == 404


def test_duplicate_email(client: TestClient):
    """Vérifie le refus d'une adresse email déjà utilisée."""

    payload = {
        "name": "Client Test",
        "email": "duplicate@test.com",
        "status": "active",
    }

    first_response = client.post("/api/clients", json=payload)
    second_response = client.post("/api/clients", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
