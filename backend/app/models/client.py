from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship, validates

from app.database import Base


class Client(Base):
    """Représente un client de la plateforme ClientPulse."""

    __tablename__ = "clients"

    # Identifiant unique du client.
    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Nom obligatoire du client.
    name = Column(
        String(120),
        nullable=False,
        index=True,
    )

    # Adresse e-mail unique.
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Informations facultatives.
    company = Column(
        String(150),
        nullable=True,
    )

    phone = Column(
        String(30),
        nullable=True,
    )

    # Statut du client avec valeur par défaut Python et SQL.
    status = Column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )

    # Date de création en UTC.
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relation : un client peut posséder plusieurs tickets.
    tickets = relationship(
        "Ticket",
        back_populates="client",
        passive_deletes=True,
    )

    @validates("name")
    def validate_name(self, key, value):
        """Nettoie et valide le nom du client."""

        if not isinstance(value, str):
            raise ValueError(
                "Le nom du client doit être une chaîne de caractères."
            )

        value = value.strip()

        if not value:
            raise ValueError("Le nom du client est obligatoire.")

        if len(value) > 120:
            raise ValueError(
                "Le nom du client ne doit pas dépasser 120 caractères."
            )

        return value

    @validates("email")
    def validate_email(self, key, value):
        """Nettoie et valide le format élémentaire de l'adresse e-mail."""

        if not isinstance(value, str):
            raise ValueError(
                "L'adresse e-mail doit être une chaîne de caractères."
            )

        value = value.strip().lower()

        if not value:
            raise ValueError("L'adresse e-mail est obligatoire.")

        if len(value) > 255:
            raise ValueError(
                "L'adresse e-mail ne doit pas dépasser 255 caractères."
            )

        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("L'adresse e-mail est invalide.")

        return value

    @validates("status")
    def validate_status(self, key, value):
        """Vérifie que le statut du client est autorisé."""

        allowed = {"active", "inactive", "prospect"}

        if not isinstance(value, str):
            raise ValueError("Le statut doit être une chaîne de caractères.")

        value = value.strip().lower()

        if value not in allowed:
            raise ValueError(
                "Le statut doit être active, inactive ou prospect."
            )

        return value
