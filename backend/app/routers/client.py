
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate

router = APIRouter(prefix="/api/clients", tags=["Clients"])


@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    existing = db.query(Client).filter(
        Client.email == str(payload.email).lower()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un client avec cette adresse email existe déjà.",
        )

    client = Client(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        company=payload.company,
        phone=payload.phone,
        status=payload.status,
    )

    db.add(client)

    try:
        db.commit()
        db.refresh(client)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée.",
        )

    return client


@router.get("", response_model=list[ClientResponse])
def list_clients(
    search: str | None = Query(default=None, max_length=120),
    client_status: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Client)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Client.name.ilike(term),
                Client.email.ilike(term),
                Client.company.ilike(term),
            )
        )

    if client_status:
        if client_status not in {"active", "inactive", "prospect"}:
            raise HTTPException(
                status_code=422,
                detail="Statut invalide : active, inactive ou prospect.",
            )
        query = query.filter(Client.status == client_status)

    return query.order_by(Client.id.desc()).offset(skip).limit(limit).all()


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client introuvable.",
        )

    return client


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
):
    client = db.get(Client, client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client introuvable.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune modification fournie.",
        )

    if "name" in changes:
        if changes["name"] is None or not changes["name"].strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le nom ne peut pas être vide.",
            )
        changes["name"] = changes["name"].strip()

    if "email" in changes:
        if changes["email"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'email ne peut pas être nul.",
            )
        changes["email"] = str(changes["email"]).lower()

        duplicate = db.query(Client).filter(
            Client.email == changes["email"],
            Client.id != client_id,
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette adresse email est déjà utilisée.",
            )

    for field, value in changes.items():
        setattr(client, field, value)

    try:
        db.commit()
        db.refresh(client)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Modification impossible : donnée déjà utilisée.",
        )

    return client


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client introuvable.",
        )

    db.delete(client)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
