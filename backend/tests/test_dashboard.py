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
    """Vérifie l'isolation des statistiques entre agents et administrateur."""

    # Créer deux clients avec des statuts différents.
    client_ids = []

    clients_data = [
        {
            "name": "Client Isolation 0",
            "email": "isolation0@dashboard-test.com",
            "status": "active",
        },
        {
            "name": "Client Isolation 1",
            "email": "isolation1@dashboard-test.com",
            "status": "prospect",
        },
    ]

    for data in clients_data:
        response = admin_client.post("/api/clients", json=data)
        assert response.status_code == 201, response.text
        client_ids.append(response.json()["id"])

    # Créer un deuxième agent.
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

    token = create_access_token(str(second_agent_id))

    with TestClient(
        app,
        headers={"Authorization": f"Bearer {token}"},
    ) as second_agent_client:

        # L'agent principal crée deux tickets pour le même client.
        for index in range(2):
            response = client.post(
                "/api/tickets",
                json={
                    "title": f"Ticket principal {index}",
                    "description": "Ticket du premier agent.",
                    "priority": "urgent",
                    "status": "open" if index == 0 else "resolved",
                    "client_id": client_ids[0],
                },
            )
            assert response.status_code == 201, response.text

        # Le deuxième agent crée un ticket pour l'autre client.
        response = second_agent_client.post(
            "/api/tickets",
            json={
                "title": "Ticket deuxième agent",
                "description": "Ticket du deuxième agent.",
                "priority": "high",
                "status": "resolved",
                "client_id": client_ids[1],
            },
        )
        assert response.status_code == 201, response.text

        # Récupérer les statistiques des deux agents.
        first_stats_response = client.get("/api/dashboard")
        assert first_stats_response.status_code == 200
        first_stats = first_stats_response.json()

        second_stats_response = second_agent_client.get("/api/dashboard")
        assert second_stats_response.status_code == 200
        second_stats = second_stats_response.json()

        # Premier agent : un seul client distinct malgré deux tickets.
        assert first_stats["clients"]["total"] == 1
        assert first_stats["clients"]["active"] == 1
        assert first_stats["clients"]["prospect"] == 0

        assert first_stats["tickets"]["total"] == 2
        assert first_stats["tickets"]["open"] == 1
        assert first_stats["tickets"]["resolved"] == 1
        assert first_stats["priorities"]["urgent"] == 2
        assert first_stats["priorities"]["high"] == 0
        assert first_stats["resolution_rate"] == 50.0

        # Deuxième agent : uniquement son propre client et son ticket.
        assert second_stats["clients"]["total"] == 1
        assert second_stats["clients"]["active"] == 0
        assert second_stats["clients"]["prospect"] == 1

        assert second_stats["tickets"]["total"] == 1
        assert second_stats["tickets"]["open"] == 0
        assert second_stats["tickets"]["resolved"] == 1
        assert second_stats["priorities"]["urgent"] == 0
        assert second_stats["priorities"]["high"] == 1
        assert second_stats["resolution_rate"] == 100.0

        # L'administrateur conserve une vue globale.
        admin_response = admin_client.get("/api/dashboard")
        assert admin_response.status_code == 200
        admin_stats = admin_response.json()

        assert admin_stats["clients"]["total"] == 2
        assert admin_stats["clients"]["active"] == 1
        assert admin_stats["clients"]["prospect"] == 1

        assert admin_stats["tickets"]["total"] == 3
        assert admin_stats["tickets"]["open"] == 1
        assert admin_stats["tickets"]["resolved"] == 2

        assert admin_stats["priorities"]["urgent"] == 2
        assert admin_stats["priorities"]["high"] == 1
        assert admin_stats["resolution_rate"] == 66.67
