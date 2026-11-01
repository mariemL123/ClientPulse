
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.client import Client
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketResponse, TicketUpdate


router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crée une réclamation associée à un client existant."""

    client = db.get(Client, payload.client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Le client associé à ce ticket est introuvable.",
        )

    ticket = Ticket(**payload.model_dump())

    if ticket.status == "resolved":
        ticket.resolved_at = datetime.now(timezone.utc)

    db.add(ticket)

    try:
        db.commit()
        db.refresh(ticket)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de créer ce ticket.",
        )

    return ticket


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    search: str | None = Query(default=None, max_length=200),
    ticket_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    client_id: int | None = Query(default=None, gt=0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les tickets avec recherche, filtres et pagination."""

    query = db.query(Ticket)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Ticket.title.ilike(term),
                Ticket.description.ilike(term),
            )
        )

    if ticket_status:
        allowed_statuses = {
            "open", "in_progress", "resolved", "closed"
        }

        if ticket_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Statut de ticket invalide.",
            )

        query = query.filter(Ticket.status == ticket_status)

    if priority:
        allowed_priorities = {"low", "medium", "high", "urgent"}

        if priority not in allowed_priorities:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Priorité invalide.",
            )

        query = query.filter(Ticket.priority == priority)

    if client_id is not None:
        query = query.filter(Ticket.client_id == client_id)

    return (
        query.order_by(Ticket.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne un ticket par son identifiant."""

    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket introuvable.",
        )

    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Modifie les informations d'un ticket."""

    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket introuvable.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune modification fournie.",
        )

    if "title" in changes:
        if changes["title"] is None or not changes["title"].strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le titre ne peut pas être vide.",
            )

        changes["title"] = changes["title"].strip()

    if "description" in changes:
        if (
            changes["description"] is None
            or not changes["description"].strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La description ne peut pas être vide.",
            )

        changes["description"] = changes["description"].strip()

    if "assigned_to" in changes and changes["assigned_to"] is not None:
        changes["assigned_to"] = changes["assigned_to"].strip() or None

    if "status" in changes:
        if changes["status"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le statut ne peut pas être nul.",
            )

        if changes["status"] == "resolved":
            if ticket.status != "resolved":
                ticket.resolved_at = datetime.now(timezone.utc)

        elif ticket.status == "resolved":
            ticket.resolved_at = None

    for field, value in changes.items():
        setattr(ticket, field, value)

    try:
        db.commit()
        db.refresh(ticket)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Modification impossible.",
        )

    return ticket


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Supprime un ticket. Réservé aux administrateurs."""

    ticket = db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket introuvable.",
        )

    db.delete(ticket)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
