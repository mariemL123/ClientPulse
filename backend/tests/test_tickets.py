"""Tests automatisés des routes de gestion des tickets."""

from datetime import datetime


def create_test_client(admin_client):
    """Crée un client de test avec les droits administrateur."""

    response = admin_client.post(
        "/api/clients",
        json={
            "name": "Client Ticket Test",
            "email": "ticket-test@example.com",
            "company": "Test Company",
            "phone": "+21612345678",
            "status": "active",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_test_ticket(api_client, client_id):
    """Crée un ticket affecté à l'agent de test."""

    response = api_client.post(
        "/api/tickets",
        json={
            "title": "Problème de connexion",
            "description": "Le client ne peut pas accéder à son compte.",
            "priority": "high",
            "status": "open",
            "client_id": client_id,
            "assigned_to": "Test Agent",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def test_create_ticket(client, admin_client):
    """Vérifie la création d'un ticket par un agent."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    assert ticket["title"] == "Problème de connexion"
    assert ticket["priority"] == "high"
    assert ticket["status"] == "open"
    assert ticket["client_id"] == client_id
    assert ticket["assigned_to"] == "Test Agent"
    assert ticket["resolved_at"] is None


def test_create_ticket_with_unknown_client(client):
    """Un ticket ne peut pas être créé pour un client inexistant."""

    response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket client inexistant",
            "description": "Ce ticket référence un client inexistant.",
            "priority": "medium",
            "status": "open",
            "client_id": 999999,
        },
    )

    assert response.status_code == 404


def test_partial_update_preserves_other_fields(client, admin_client):
    """La modification du statut conserve les autres informations."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200, response.text

    updated_ticket = response.json()

    assert updated_ticket["status"] == "in_progress"
    assert updated_ticket["title"] == "Problème de connexion"
    assert updated_ticket["priority"] == "high"
    assert updated_ticket["assigned_to"] == "Test Agent"
    assert updated_ticket["resolved_at"] is None


def test_resolve_ticket_sets_resolved_at(client, admin_client):
    """La résolution d'un ticket renseigne sa date de résolution."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"status": "resolved"},
    )

    assert response.status_code == 200, response.text

    resolved_ticket = response.json()

    assert resolved_ticket["status"] == "resolved"
    assert resolved_ticket["resolved_at"] is not None
    assert resolved_ticket["title"] == "Problème de connexion"

    datetime.fromisoformat(
        resolved_ticket["resolved_at"].replace("Z", "+00:00")
    )


def test_agent_cannot_assign_ticket_to_another_user(client, admin_client):
    """Un agent ne peut pas créer un ticket au nom d'un autre agent."""

    client_id = create_test_client(admin_client)

    response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket non autorisé",
            "description": "Tentative d'affectation à un autre utilisateur.",
            "priority": "medium",
            "status": "open",
            "client_id": client_id,
            "assigned_to": "Autre Agent",
        },
    )

    assert response.status_code == 403


def test_agent_cannot_delete_ticket(client, admin_client):
    """Un agent ne peut pas supprimer un ticket."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    response = client.delete(f"/api/tickets/{ticket['id']}")

    assert response.status_code == 403


def test_agent_cannot_modify_ticket_assignment(client, admin_client):
    """Un agent ne peut pas modifier l'affectation d'un ticket."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"assigned_to": "Autre Agent"},
    )

    assert response.status_code == 403


def test_admin_can_list_tickets(admin_client, client):
    """Un administrateur peut consulter les tickets."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)

    response = admin_client.get("/api/tickets")

    assert response.status_code == 200, response.text
    assert any(item["id"] == ticket["id"] for item in response.json())

def test_ticket_description_max_length(client, admin_client):
    """Une description de 10 000 caractères est acceptée."""

    client_id = create_test_client(admin_client)

    response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket description longue",
            "description": "A" * 10_000,
            "priority": "medium",
            "status": "open",
            "client_id": client_id,
        },
    )

    assert response.status_code == 201, response.text
    assert len(response.json()["description"]) == 10_000


def test_ticket_description_exceeding_max_length(client, admin_client):
    """Une description de 10 001 caractères est rejetée."""

    client_id = create_test_client(admin_client)

    response = client.post(
        "/api/tickets",
        json={
            "title": "Ticket description trop longue",
            "description": "A" * 10_001,
            "priority": "medium",
            "status": "open",
            "client_id": client_id,
        },
    )

    assert response.status_code == 422, response.text


def test_admin_can_delete_ticket(admin_client, client):
    """Un administrateur peut supprimer un ticket."""

    client_id = create_test_client(admin_client)
    ticket = create_test_ticket(client, client_id)
    ticket_id = ticket["id"]

    delete_response = admin_client.delete(f"/api/tickets/{ticket_id}")
    assert delete_response.status_code == 204, delete_response.text

    get_response = admin_client.get(f"/api/tickets/{ticket_id}")
    assert get_response.status_code == 404, get_response.text


def test_admin_cannot_delete_unknown_ticket(admin_client):
    """La suppression d'un ticket inexistant renvoie 404."""

    response = admin_client.delete("/api/tickets/999999")

    assert response.status_code == 404, response.text
