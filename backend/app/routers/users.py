
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserStatusUpdate


router = APIRouter(
    prefix="/api/users",
    tags=["Users Administration"],
    dependencies=[Depends(require_admin)],
)


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

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

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

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    if user.id == current_user.id and not status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )

    user.is_active = status_data.is_active

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de modifier le statut du compte.",
        )

    return user
