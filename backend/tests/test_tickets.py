
from tests.conftest import client as client_fixture  # Référence informative au fixture


def create_test_client(api_client):
    """Crée un client de test et retourne son identifiant."""

    response = api_client.post(
        "/api/clients",
        json={
            "name": "Client Ticket Test",
            "email": "ticket-test@example.com",
            "company": "Test Company",
            "phone": "+21612345678",
            "status": "active",
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def create_test_ticket(api_client, client_id):
    """Crée un ticket de test associé à un client."""

    response = api_client.post(
        "/api/tickets",
        json={
            "title": "Problème de connexion",
            "description": "Le client ne peut pas accéder à son compte.",
            "priority": "high",
            "status": "open",
            "client_id": client_id,
            "assigned_to": "Support technique",
        },
    )

    assert response.status_code == 201
    return response.json()


def test_create_ticket(client):
    """Vérifie la création d'un ticket."""

    client_id = create_test_client(client)
    ticket = create_test_ticket(client, client_id)

    assert ticket["title"] == "Problème de connexion"
    assert ticket["priority"] == "high"
    assert ticket["status"] == "open"
    assert ticket["client_id"] == client_id
    assert ticket["resolved_at"] is None


def test_create_ticket_with_unknown_client(client):
    """Vérifie le refus d'un client inexistant."""

    response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket invalide",
            "description": "Ce ticket référence un client inexistant.",
            "priority": "medium",
            "status": "open",
            "client_id": 999999,
        },
    )

    assert response.status_code == 404


def test_partial_update_preserves_other_fields(client):
    """Vérifie qu'un PATCH ne modifie que les champs transmis."""

    client_id = create_test_client(client)
    ticket = create_test_ticket(client, client_id)

    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200

    updated_ticket = response.json()

    assert updated_ticket["status"] == "in_progress"
    assert updated_ticket["title"] == "Problème de connexion"
    assert updated_ticket["priority"] == "high"
    assert updated_ticket["assigned_to"] == "Support technique"
    assert updated_ticket["resolved_at"] is None


def test_resolve_ticket_sets_resolved_at(client):
    """Vérifie que la résolution renseigne automatiquement sa date."""

    client_id = create_test_client(client)
    ticket = create_test_ticket(client, client_id)

    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"status": "resolved"},
    )

    assert response.status_code == 200

    resolved_ticket = response.json()

    assert resolved_ticket["status"] == "resolved"
    assert resolved_ticket["resolved_at"] is not None
    assert resolved_ticket["title"] == "Problème de connexion"
