
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.config import settings


# Algorithme de signature des tokens JWT.
ALGORITHM = "HS256"

# Gestion sécurisée des mots de passe avec Argon2.
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Retourne le hash Argon2 d'un mot de passe."""

    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide.")

    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Vérifie un mot de passe à partir de son hash."""

    if not plain_password or not hashed_password:
        return False

    return password_hash.verify(
        plain_password,
        hashed_password,
    )



def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    token_version: int = 0,
) -> str:
    """Génère un JWT signé avec expiration et version de sécurité."""

    if not subject:
        raise ValueError("Le sujet du token est obligatoire.")

    if isinstance(token_version, bool) or not isinstance(token_version, int):
        raise ValueError("La version du token doit être un entier.")

    if token_version < 0:
        raise ValueError("La version du token ne peut pas être négative.")

    duration = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    if duration <= 0:
        raise ValueError("La durée du token doit être positive.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": subject,
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=duration),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """Décode et vérifie un JWT.

    Retourne None si le token est invalide ou expiré.
    """

    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

    except JWTError:
        return None
