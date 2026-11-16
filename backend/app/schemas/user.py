
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
                raise ValueError(
                    "Le nom complet doit contenir au moins 2 caractères."
                )

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
    must_change_password: bool
    avatar_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserStatusUpdate(BaseModel):
    """Données nécessaires pour activer ou désactiver un compte."""

    is_active: bool


class TokenResponse(BaseModel):
    """Réponse contenant le JWT."""

    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Données nécessaires au changement du mot de passe."""

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError(
                "Les nouveaux mots de passe ne correspondent pas."
            )

        if self.new_password == self.current_password:
            raise ValueError(
                "Le nouveau mot de passe doit être différent de l'ancien."
            )

        return self


class PasswordResetResponse(BaseModel):
    """Mot de passe temporaire communiqué une seule fois à l'administrateur."""

    temporary_password: str
