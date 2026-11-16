
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import ALGORITHM
from app.database import get_db
from app.models.user import User


# Schéma Bearer utilisé pour transmettre le JWT.
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Identifie l'utilisateur et vérifie la validité de son JWT."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants d'authentification invalides.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        subject = payload.get("sub")
        token_version = payload.get("ver", 0)

        if subject is None:
            raise credentials_exception

        # Refuse les versions malformées ou de type booléen.
        if isinstance(token_version, bool) or not isinstance(token_version, int):
            raise credentials_exception

        if token_version < 0:
            raise credentials_exception

        user_id = int(subject)

    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur est désactivé.",
        )

    # Invalide les JWT créés avant une réinitialisation du mot de passe.
    if token_version != user.token_version:
        raise credentials_exception

    return user


def get_fully_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Bloque les fonctionnalités normales jusqu'au changement du mot de passe."""

    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )

    return current_user


def require_admin(
    current_user: User = Depends(get_fully_authenticated_user),
) -> User:
    """Autorise uniquement les administrateurs pleinement authentifiés."""

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )

    return current_user
