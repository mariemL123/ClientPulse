
"""Routes d'administration des utilisateurs et de leurs avatars."""

import logging
import secrets
import string

from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.user import (
    PasswordResetResponse,
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.services import file_storage


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["Users Administration"],
    dependencies=[Depends(require_admin)],
)


def _delete_avatar_safely(storage_key: str | None) -> None:
    """Supprime un avatar sans annuler une opération déjà validée."""

    if not storage_key:
        return

    try:
        file_storage.delete_stored_file("avatars", storage_key)
    except Exception:
        logger.exception(
            "Impossible de supprimer l'avatar stocké : %s",
            storage_key,
        )


def generate_temporary_password() -> str:
    """Génère un mot de passe temporaire sécurisé de 24 caractères."""

    alphabet = string.ascii_letters + string.digits

    # Garantit au moins une minuscule, une majuscule et un chiffre.
    characters = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]

    # Complète jusqu'à 24 caractères.
    characters.extend(
        secrets.choice(alphabet)
        for _ in range(21)
    )

    # Mélange les caractères de façon cryptographiquement sûre.
    secrets.SystemRandom().shuffle(characters)

    return "".join(characters)


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
    """Protège le dernier administrateur actif."""

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

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

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
def list_users(
    db: Session = Depends(get_db),
):
    """Retourne la liste de tous les utilisateurs."""

    return (
        db.query(User)
        .order_by(User.id.asc())
        .all()
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Retourne un utilisateur à partir de son identifiant."""

    return get_user_or_404(user_id, db)


@router.post(
    "/{user_id}/password/reset",
    response_model=PasswordResetResponse,
)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Réinitialise le mot de passe d'un utilisateur."""

    user = get_user_or_404(user_id, db)

    temporary_password = generate_temporary_password()

    try:
        user.hashed_password = hash_password(temporary_password)
        user.must_change_password = True
        user.password_changed_at = None
        user.token_version += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return PasswordResetResponse(
        temporary_password=temporary_password,
    )


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

    if new_name is not None and new_name != user.full_name:
        ensure_unique_full_name(new_name, user.id, db)

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


@router.put(
    "/{user_id}/avatar",
    response_model=UserResponse,
)
async def update_user_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Ajoute ou remplace l'avatar d'un utilisateur."""

    user = get_user_or_404(user_id, db)

    try:
        stored_file = await file_storage.save_avatar(file)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except OSError as exc:
        logger.exception("Erreur de stockage du nouvel avatar.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible d'enregistrer l'avatar.",
        ) from exc

    old_storage_key = user.avatar_path

    try:
        user.avatar_path = stored_file.storage_key

        db.commit()
        db.refresh(user)

    except Exception as exc:
        db.rollback()

        _delete_avatar_safely(stored_file.storage_key)

        logger.exception(
            "Impossible d'enregistrer l'avatar de l'utilisateur %s.",
            user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de mettre à jour l'avatar.",
        ) from exc

    if old_storage_key != stored_file.storage_key:
        _delete_avatar_safely(old_storage_key)

    return user


@router.delete(
    "/{user_id}/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_avatar(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Supprime l'avatar d'un utilisateur."""

    user = get_user_or_404(user_id, db)
    old_storage_key = user.avatar_path

    if not old_storage_key:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        user.avatar_path = None
        db.commit()

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Impossible de supprimer l'avatar de l'utilisateur %s.",
            user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de supprimer l'avatar.",
        ) from exc

    _delete_avatar_safely(old_storage_key)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    """Supprime un utilisateur et gère ses tickets affectés."""

    user = get_user_or_404(user_id, db)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte.",
        )

    ensure_last_admin_protection(user, db)

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

    # Conserve la clé avant la suppression de l'utilisateur.
    avatar_storage_key = user.avatar_path

    try:
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

    # Le fichier est supprimé uniquement après validation de la transaction.
    _delete_avatar_safely(avatar_storage_key)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
