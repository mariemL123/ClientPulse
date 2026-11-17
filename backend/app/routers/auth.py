"""Routes d'authentification et de gestion des avatars."""

import logging
import mimetypes

from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.rate_limiter import limiter
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    TokenResponse,
    UserLogin,
    UserResponse,
)
from app.services import file_storage


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


def _delete_avatar_safely(storage_key: str | None) -> None:
    """Supprime un avatar sans masquer une erreur déjà traitée."""

    if not storage_key:
        return

    try:
        file_storage.delete_stored_file(
            "avatars",
            storage_key,
        )
    except Exception:
        logger.exception(
            "Impossible de supprimer un ancien avatar."
        )


@router.post(
    "/login",
    response_model=TokenResponse,
)
@limiter.limit("5/minute")
def login(
    request: Request,
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """Authentifie un utilisateur actif et retourne un JWT."""

    email = str(credentials.email).strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if (
        user is None
        or not verify_password(
            credentials.password,
            user.hashed_password,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse e-mail ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé.",
        )

    access_token = create_access_token(
        str(user.id),
        token_version=user.token_version,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Retourne le profil du compte connecté."""

    return current_user


@router.post(
    "/change-password",
    response_model=TokenResponse,
)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change le mot de passe et invalide les anciens JWT."""

    if not verify_password(
        payload.current_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le mot de passe actuel est incorrect.",
        )

    current_user.hashed_password = hash_password(
        payload.new_password
    )
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.now(timezone.utc)
    current_user.token_version += 1

    new_access_token = create_access_token(
        str(current_user.id),
        token_version=current_user.token_version,
    )

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
    )


@router.put(
    "/me/avatar",
    response_model=UserResponse,
)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ajoute ou remplace l'avatar de l'utilisateur connecté."""

    old_storage_key = current_user.avatar_path

    try:
        stored_file = await file_storage.save_avatar(file)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except OSError as exc:
        logger.exception("Erreur de stockage pendant l'upload avatar.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de stocker cet avatar.",
        ) from exc

    current_user.avatar_path = stored_file.storage_key

    try:
        db.commit()
        db.refresh(current_user)

    except SQLAlchemyError:
        db.rollback()

        # Le nouveau fichier n'est pas référencé en base :
        # il doit donc être supprimé.
        _delete_avatar_safely(stored_file.storage_key)

        raise

    # L'ancien fichier n'est supprimé qu'après le commit.
    _delete_avatar_safely(old_storage_key)

    return current_user


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_my_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime l'avatar de l'utilisateur connecté."""

    old_storage_key = current_user.avatar_path

    if not old_storage_key:
        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )

    current_user.avatar_path = None

    try:
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise

    # La référence en base est supprimée avant le fichier physique.
    _delete_avatar_safely(old_storage_key)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.get(
    "/users/{user_id}/avatar",
)

def get_user_avatar(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne l'avatar d'un utilisateur authentifi?."""

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None or not user.avatar_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar introuvable.",
        )

    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=300",
    }

    content_type = (
        mimetypes.guess_type(user.avatar_path)[0]
        or "application/octet-stream"
    )

    # En mode Supabase, l'avatar est r?cup?r? c?t? serveur.
    # Le bucket reste priv? : aucune URL publique n'est expos?e.
    if file_storage.settings.STORAGE_BACKEND == "supabase":
        try:
            content = file_storage.get_supabase_avatar(user.avatar_path)

        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar introuvable.",
            ) from exc

        except ValueError as exc:
            logger.warning(
                "Cl? de stockage avatar invalide pour user_id=%s.",
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar introuvable.",
            ) from exc

        except OSError as exc:
            logger.exception(
                "Erreur de lecture Supabase pour user_id=%s.",
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Impossible de lire cet avatar.",
            ) from exc

        return Response(
            content=content,
            media_type=content_type,
            headers=headers,
        )

    # En mode local, le comportement historique est conserv?.
    try:
        avatar_path = file_storage.get_storage_path(
            "avatars",
            user.avatar_path,
        )

        if not avatar_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar introuvable.",
            )

    except ValueError as exc:
        logger.warning(
            "Cl? de stockage avatar invalide pour user_id=%s.",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar introuvable.",
        ) from exc

    except OSError as exc:
        logger.exception(
            "Erreur d'acc?s au stockage avatar pour user_id=%s.",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de lire cet avatar.",
        ) from exc

    return FileResponse(
        path=avatar_path,
        media_type=content_type,
        headers=headers,
    )
