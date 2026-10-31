
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.ticket import Ticket


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("")
def get_dashboard_statistics(db: Session = Depends(get_db)):
    """Retourne les statistiques globales de ClientPulse."""

    # Nombre total de clients.
    total_clients = db.query(func.count(Client.id)).scalar() or 0

    # Répartition des clients par statut.
    client_statuses = (
        db.query(Client.status, func.count(Client.id))
        .group_by(Client.status)
        .all()
    )

    clients = {
        "total": total_clients,
        "active": 0,
        "inactive": 0,
        "prospect": 0,
    }

    for status_name, count in client_statuses:
        if status_name in clients:
            clients[status_name] = count

    # Nombre total de tickets.
    total_tickets = db.query(func.count(Ticket.id)).scalar() or 0

    # Répartition des tickets par statut.
    ticket_statuses = (
        db.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )

    tickets = {
        "total": total_tickets,
        "open": 0,
        "in_progress": 0,
        "resolved": 0,
        "closed": 0,
    }

    for status_name, count in ticket_statuses:
        if status_name in tickets:
            tickets[status_name] = count

    # Répartition des tickets par priorité.
    ticket_priorities = (
        db.query(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )

    priorities = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "urgent": 0,
    }

    for priority_name, count in ticket_priorities:
        if priority_name in priorities:
            priorities[priority_name] = count

    # Calcul du taux de résolution.
    resolution_rate = (
        round(
            (tickets["resolved"] + tickets["closed"])
            / total_tickets * 100,
            2,
        )
        if total_tickets > 0
        else 0.0
    )

    return {
        "clients": clients,
        "tickets": tickets,
        "priorities": priorities,
        "resolution_rate": resolution_rate,
    }
