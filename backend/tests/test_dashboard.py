from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


def test_dashboard_statistics(client, admin_client):
    """Vérifie les statistiques du tableau de bord."""

    # Créer les clients avec les droits administrateur.
    clients_data = [
        {
            "name": "Client actif",
            "email": "actif@dashboard-test.com",
            "status": "active",
        },
        {
            "name": "Client prospect",
            "email": "prospect@dashboard-test.com",
            "status": "prospect",
        },
    ]

    client_ids = []

    for data in clients_data:
        response = admin_client.post("/api/clients", json=data)
        assert response.status_code == 201, response.text
        client_ids.append(response.json()["id"])

    # Créer les tickets avec le compte agent.
    tickets_data = [
        {
            "title": "Incident urgent",
            "description": "Incident nécessitant une intervention.",
            "priority": "urgent",
            "status": "open",
            "client_id": client_ids[0],
        },
        {
            "title": "Demande résolue",
            "description": "Demande traitée par le support.",
            "priority": "high",
            "status": "resolved",
            "client_id": client_ids[1],
        },
    ]

    for data in tickets_data:
        response = client.post("/api/tickets", json=data)
        assert response.status_code == 201, response.text

    # Interroger le tableau de bord avec le compte agent.
    response = client.get("/api/dashboard")

    assert response.status_code == 200, response.text

    statistics = response.json()

    assert statistics["clients"]["total"] == 2
    assert statistics["clients"]["active"] == 1
    assert statistics["clients"]["prospect"] == 1

    assert statistics["tickets"]["total"] == 2
    assert statistics["tickets"]["open"] == 1
    assert statistics["tickets"]["resolved"] == 1

    assert statistics["priorities"]["urgent"] == 1
    assert statistics["priorities"]["high"] == 1

    assert statistics["resolution_rate"] == 50.0


def test_dashboard_empty_database(client):
    """Vérifie le comportement avec une base vide."""

    response = client.get("/api/dashboard")

    assert response.status_code == 200, response.text

    statistics = response.json()

    assert statistics["clients"]["total"] == 0
    assert statistics["tickets"]["total"] == 0
    assert statistics["resolution_rate"] == 0.0

def test_dashboard_agent_statistics_are_isolated(client, admin_client):
    """V?rifie l'isolation des tickets entre agents et la vue globale admin."""

    # Cr?er deux clients accessibles ? tous les utilisateurs.
    client_ids = []
    for index in range(2):
        response = admin_client.post(
            "/api/clients",
            json={
                "name": f"Client Isolation {index}",
                "email": f"isolation{index}@dashboard-test.com",
                "status": "active",
            },
        )
        assert response.status_code == 201, response.text
        client_ids.append(response.json()["id"])

    # Cr?er un deuxi?me agent via l'API d'administration.
    response = admin_client.post(
        "/api/users/",
        json={
            "full_name": "Agent Deux",
            "email": "agent.deux@dashboard-test.com",
            "password": "AgentPassword123!",
        },
    )
    assert response.status_code == 201, response.text
    second_agent_id = response.json()["id"]

    # Cr?er une session authentifi?e pour le deuxi?me agent.
    token = create_access_token(str(second_agent_id))
    with TestClient(
        app,
        headers={"Authorization": f"Bearer {token}"},
    ) as second_agent_client:

        # L'agent principal cr?e son propre ticket.
        response = client.post(
            "/api/tickets",
            json={
                "title": "Ticket agent principal",
                "description": "Ticket r?serv? au premier agent.",
                "priority": "urgent",
                "status": "open",
                "client_id": client_ids[0],
            },
        )
        assert response.status_code == 201, response.text

        # Le deuxi?me agent cr?e son propre ticket.
        response = second_agent_client.post(
            "/api/tickets",
            json={
                "title": "Ticket deuxi?me agent",
                "description": "Ticket r?serv? au deuxi?me agent.",
                "priority": "high",
                "status": "resolved",
                "client_id": client_ids[1],
            },
        )
        assert response.status_code == 201, response.text

        # Chaque agent ne voit que ses propres statistiques de tickets.
        first_stats_response = client.get("/api/dashboard")
        assert first_stats_response.status_code == 200, first_stats_response.text
        first_stats = first_stats_response.json()

        second_stats_response = second_agent_client.get("/api/dashboard")
        assert second_stats_response.status_code == 200, second_stats_response.text
        second_stats = second_stats_response.json()

        assert first_stats["tickets"]["total"] == 1
        assert first_stats["tickets"]["open"] == 1
        assert first_stats["tickets"]["resolved"] == 0
        assert first_stats["priorities"]["urgent"] == 1
        assert first_stats["priorities"]["high"] == 0

        assert second_stats["tickets"]["total"] == 1
        assert second_stats["tickets"]["open"] == 0
        assert second_stats["tickets"]["resolved"] == 1
        assert second_stats["priorities"]["urgent"] == 0
        assert second_stats["priorities"]["high"] == 1

        # Les statistiques des clients restent globales pour les agents.
        assert first_stats["clients"]["total"] == 2
        assert second_stats["clients"]["total"] == 2

        # L'administrateur conserve une vue globale sur tous les tickets.
        admin_response = admin_client.get("/api/dashboard")
        assert admin_response.status_code == 200, admin_response.text
        admin_stats = admin_response.json()

        assert admin_stats["clients"]["total"] == 2
        assert admin_stats["tickets"]["total"] == 2
        assert admin_stats["tickets"]["open"] == 1
        assert admin_stats["tickets"]["resolved"] == 1
        assert admin_stats["priorities"]["urgent"] == 1
        assert admin_stats["priorities"]["high"] == 1
        assert admin_stats["resolution_rate"] == 50.0
