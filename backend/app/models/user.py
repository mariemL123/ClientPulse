from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    true,
)
from sqlalchemy.orm import validates

from app.database import Base


class User(Base):
    """Utilisateur de la plateforme ClientPulse."""

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'agent')",
            name="ck_users_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(120), nullable=False)

    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Seul le hash Argon2 sera enregistré en base de données.
    hashed_password = Column(String(255), nullable=False)

    # Valeur par défaut côté Python et directement dans la base SQL.
    role = Column(
        String(20),
        nullable=False,
        default="agent",
        server_default="agent",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @validates("full_name")
    def validate_full_name(self, key, value):
        """Vérifie et nettoie le nom complet."""
        if not isinstance(value, str):
            raise ValueError("Le nom complet doit être une chaîne de caractères.")

        value = value.strip()

        if not value:
            raise ValueError("Le nom complet est obligatoire.")

        return value

    @validates("email")
    def validate_email(self, key, value):
        """Normalise et vérifie l'adresse e-mail."""
        if not isinstance(value, str):
            raise ValueError("L'adresse e-mail doit être une chaîne de caractères.")

        value = value.strip().lower()

        if not value:
            raise ValueError("L'adresse e-mail est obligatoire.")

        return value

    @validates("role")
    def validate_role(self, key, value):
        """Limite les rôles aux valeurs autorisées."""
        allowed_roles = {"admin", "agent"}

        if value not in allowed_roles:
            raise ValueError(
                "Le rôle doit être admin ou agent."
            )

        return value
