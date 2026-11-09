from fastapi.testclient import TestClient


CLIENT_PAYLOAD = {
    "name": "Entreprise Test",
    "email": "entreprise@test.com",
    "company": "Test Company",
    "phone": "+21612345678",
    "status": "active",
}


def test_admin_can_create_client(admin_client: TestClient):
    """Un administrateur peut créer un client."""

    response = admin_client.post("/api/clients", json=CLIENT_PAYLOAD)

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Entreprise Test"
    assert data["email"] == "entreprise@test.com"
    assert data["status"] == "active"
    assert "id" in data


def test_agent_cannot_create_client(client: TestClient):
    """Un agent ne peut pas créer de client."""

    response = client.post("/api/clients", json=CLIENT_PAYLOAD)

    assert response.status_code == 403


def test_agent_can_list_all_clients(
    admin_client: TestClient,
    client: TestClient,
):
    """Un agent peut consulter tous les clients."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    response = client.get("/api/clients")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Entreprise Test"


def test_agent_can_get_client(
    admin_client: TestClient,
    client: TestClient,
):
    """Un agent peut consulter la fiche d'un client."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]
    response = client.get(f"/api/clients/{client_id}")

    assert response.status_code == 200
    assert response.json()["id"] == client_id


def test_admin_can_update_client(admin_client: TestClient):
    """Un administrateur peut modifier un client."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = admin_client.patch(
        f"/api/clients/{client_id}",
        json={
            "company": "Nouvelle Entreprise",
            "status": "prospect",
        },
    )

    assert response.status_code == 200
    assert response.json()["company"] == "Nouvelle Entreprise"
    assert response.json()["status"] == "prospect"


def test_agent_cannot_update_client(
    admin_client: TestClient,
    client: TestClient,
):
    """Un agent ne peut pas modifier un client."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = client.patch(
        f"/api/clients/{client_id}",
        json={"company": "Modification interdite"},
    )
    assert response.status_code == 403

    # Vérifie que les données n'ont pas été modifiées.
    verification = admin_client.get(f"/api/clients/{client_id}")

    assert verification.status_code == 200
    assert verification.json()["company"] == "Test Company"


def test_admin_can_delete_client(admin_client: TestClient):
    """Un administrateur peut supprimer un client."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = admin_client.delete(f"/api/clients/{client_id}")

    assert response.status_code == 204

    verification = admin_client.get(f"/api/clients/{client_id}")
    assert verification.status_code == 404


def test_agent_cannot_delete_client(
    admin_client: TestClient,
    client: TestClient,
):
    """Un agent ne peut pas supprimer un client."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201

    client_id = create_response.json()["id"]

    response = client.delete(f"/api/clients/{client_id}")
    assert response.status_code == 403

    # Le client doit toujours être consultable.
    verification = client.get(f"/api/clients/{client_id}")
    assert verification.status_code == 200


def test_duplicate_email(admin_client: TestClient):
    """Une adresse e-mail déjà utilisée doit être refusée."""

    first_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    second_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_unauthenticated_user_cannot_list_clients(
    unauthenticated_client: TestClient,
):
    """Un utilisateur sans token ne peut pas consulter les clients."""

    response = unauthenticated_client.get("/api/clients")

    assert response.status_code == 401

def test_admin_cannot_delete_client_with_tickets(
    admin_client: TestClient,
    client: TestClient,
):
    """Un client associ? ? un ticket ne peut pas ?tre supprim?."""

    create_response = admin_client.post(
        "/api/clients",
        json=CLIENT_PAYLOAD,
    )
    assert create_response.status_code == 201, create_response.text
    client_id = create_response.json()["id"]

    ticket_response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket li? au client",
            "description": "Ce ticket doit emp?cher la suppression du client.",
            "priority": "high",
            "status": "open",
            "client_id": client_id,
        },
    )
    assert ticket_response.status_code == 201, ticket_response.text
    ticket_id = ticket_response.json()["id"]

    delete_response = admin_client.delete(f"/api/clients/{client_id}")
    assert delete_response.status_code == 409, delete_response.text

    client_check = admin_client.get(f"/api/clients/{client_id}")
    assert client_check.status_code == 200, client_check.text

    ticket_check = client.get(f"/api/tickets/{ticket_id}")
    assert ticket_check.status_code == 200, ticket_check.text
