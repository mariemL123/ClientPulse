
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal

from app.core.dependencies import require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)


router = APIRouter(
    prefix="/api/users",
    tags=["Users Administration"],
    dependencies=[Depends(require_admin)],
)


def get_user_or_404(user_id: int, db: Session) -> User:
    """Récupère un utilisateur ou renvoie une erreur 404."""

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    return user


def ensure_unique_full_name(
    full_name: str,
    user_id: int,
    db: Session,
) -> None:
    """Empêche les affectations ambiguës entre utilisateurs."""

    duplicate = (
        db.query(User)
        .filter(
            User.full_name == full_name,
            User.id != user_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom est déjà utilisé par un autre utilisateur.",
        )


def ensure_last_admin_protection(
    user: User,
    db: Session,
    operation: Literal["supprimer", "désactiver"] = "supprimer",
) -> None:
    """Empêche la suppression ou la désactivation du dernier administrateur actif."""

    if user.role != "admin" or not user.is_active:
        return

    active_admins = (
        db.query(User)
        .filter(
            User.role == "admin",
            User.is_active.is_(True),
        )
        .count()
    )

    if active_admins <= 1:
        action = "supprimer" if operation == "supprimer" else "désactiver"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de {action} le dernier administrateur actif.",
        )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Crée un compte agent. Réservé aux administrateurs."""

    email = str(user_data.email).strip().lower()

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà utilisée.",
        )

    user = User(
        full_name=user_data.full_name.strip(),
        email=email,
        hashed_password=hash_password(user_data.password),
        role="agent",
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà utilisée.",
        )

    return user


@router.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    """Retourne la liste de tous les utilisateurs."""

    return db.query(User).order_by(User.id.asc()).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Retourne un utilisateur à partir de son identifiant."""

    return get_user_or_404(user_id, db)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
):
    """Modifie le nom et/ou l'adresse e-mail d'un utilisateur."""

    user = get_user_or_404(user_id, db)
    changes = user_data.model_dump(exclude_unset=True)

    new_name = changes.get("full_name")
    new_email = changes.get("email")

    # Vérifie que le changement de nom ne crée pas d'ambiguïté.
    if new_name is not None and new_name != user.full_name:
        ensure_unique_full_name(new_name, user.id, db)

        # Si l'ancien nom est déjà partagé, les tickets ne peuvent
        # pas être attribués de façon fiable à ce seul utilisateur.
        duplicate_old_name = (
            db.query(User)
            .filter(
                User.full_name == user.full_name,
                User.id != user.id,
            )
            .first()
        )

        if duplicate_old_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Impossible de renommer cet utilisateur : "
                    "son nom actuel est partagé avec un autre compte."
                ),
            )

    if new_email is not None and new_email != user.email:
        existing_email = (
            db.query(User)
            .filter(
                User.email == new_email,
                User.id != user.id,
            )
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette adresse e-mail est déjà utilisée.",
            )

    try:
        # Synchronise les affectations avant de modifier le nom.
        if new_name is not None and new_name != user.full_name:
            db.query(Ticket).filter(
                Ticket.assigned_to == user.full_name
            ).update(
                {Ticket.assigned_to: new_name},
                synchronize_session=False,
            )

            user.full_name = new_name

        if new_email is not None:
            user.email = new_email

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une donnée fournie est déjà utilisée.",
        )
    except Exception:
        db.rollback()
        raise

    return user


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
)
def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Active ou désactive un compte utilisateur."""

    user = get_user_or_404(user_id, db)

    if user.id == current_user.id and not status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )

    if not status_data.is_active:
        ensure_last_admin_protection(
            user,
            db,
            operation="désactiver",
        )

    try:
        user.is_active = status_data.is_active
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de modifier le statut du compte.",
        )

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(
    user_id: int,
    replacement_user_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Supprime un utilisateur.

    Si des tickets lui sont affectés, un agent actif de remplacement
    doit être fourni avec replacement_user_id.
    """

    user = get_user_or_404(user_id, db)

    # Protection contre l'auto-suppression.
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte.",
        )

    ensure_last_admin_protection(user, db)

    # Le nom doit identifier un seul compte pour éviter de toucher
    # aux tickets d'un autre utilisateur.
    duplicate_name = (
        db.query(User)
        .filter(
            User.full_name == user.full_name,
            User.id != user.id,
        )
        .first()
    )

    if duplicate_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Suppression impossible : le nom de cet utilisateur "
                "est partagé avec un autre compte."
            ),
        )

    assigned_tickets = (
        db.query(Ticket)
        .filter(Ticket.assigned_to == user.full_name)
    )

    ticket_count = assigned_tickets.count()

    replacement = None

    if ticket_count > 0:
        if replacement_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        "Cet utilisateur possède des tickets. "
                        "Choisissez un agent actif pour les réaffecter."
                    ),
                    "ticket_count": ticket_count,
                    "requires_replacement": True,
                },
            )

        replacement = get_user_or_404(replacement_user_id, db)

        if replacement.id == user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'agent de remplacement doit être différent.",
            )

        if replacement.role != "agent" or not replacement.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="L'agent de remplacement doit être actif.",
            )

        ensure_unique_full_name(
            replacement.full_name,
            replacement.id,
            db,
        )

    elif replacement_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun ticket ne nécessite de réaffectation.",
        )

    try:
        # La réaffectation et la suppression sont atomiques.
        if ticket_count > 0 and replacement is not None:
            assigned_tickets.update(
                {Ticket.assigned_to: replacement.full_name},
                synchronize_session=False,
            )

        db.delete(user)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de supprimer cet utilisateur.",
        )
    except Exception:
        db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
