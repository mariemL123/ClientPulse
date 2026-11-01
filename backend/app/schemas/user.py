
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Données nécessaires à la création d'un compte."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Identifiants de connexion."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Informations publiques d'un utilisateur."""

    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserStatusUpdate(BaseModel):
    """Données nécessaires pour activer ou désactiver un compte."""

    is_active: bool


class TokenResponse(BaseModel):
    """Réponse contenant le JWT."""

    access_token: str
    token_type: str = "bearer"
