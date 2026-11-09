
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class UserCreate(BaseModel):
    """Données nécessaires à la création d'un compte agent."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Identifiants de connexion."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Modification du nom et/ou de l'adresse e-mail."""

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("Au moins un champ doit être fourni.")

        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Le champ {field} ne peut pas être nul.")

        if self.full_name is not None:
            self.full_name = self.full_name.strip()
            if len(self.full_name) < 2:
                raise ValueError("Le nom complet doit contenir au moins 2 caractères.")

        if self.email is not None:
            self.email = str(self.email).strip().lower()

        return self


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
