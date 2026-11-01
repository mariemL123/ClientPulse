
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.core.security import ALGORITHM


# Schéma Bearer : Swagger transmettra le JWT dans Authorization.
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Identifie l'utilisateur à partir de son JWT."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants d'authentification invalides.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extraction du token depuis l'en-tête Authorization.
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        subject = payload.get("sub")

        if subject is None:
            raise credentials_exception

        user_id = int(subject)

    except (JWTError, ValueError):
        raise credentials_exception

    # Recherche de l'utilisateur correspondant au token.
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    # Un compte désactivé ne peut pas accéder à l'API.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur est désactivé.",
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Autorise uniquement les administrateurs."""

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )

    return current_user
