
def test_dashboard_statistics(client):
    """Vérifie les statistiques du tableau de bord."""

    # Créer deux clients avec des statuts différents.
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
        response = client.post("/api/clients", json=data)
        assert response.status_code == 201
        client_ids.append(response.json()["id"])

    # Créer deux tickets avec des priorités différentes.
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
        assert response.status_code == 201

    # Interroger le tableau de bord.
    response = client.get("/api/dashboard")

    assert response.status_code == 200

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

    assert response.status_code == 200

    statistics = response.json()

    assert statistics["clients"]["total"] == 0
    assert statistics["tickets"]["total"] == 0
    assert statistics["resolution_rate"] == 0.0
