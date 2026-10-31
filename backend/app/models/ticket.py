
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, validates

from app.database import Base


class Ticket(Base):
    """Représente une réclamation ou un problème client."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)

    priority = Column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="open",
        index=True,
    )

    # Chaque ticket doit être associé à un client existant.
    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assigned_to = Column(String(120), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relation avec le modèle Client.
    client = relationship("Client", back_populates="tickets")

    @validates("title")
    def validate_title(self, key, value):
        value = value.strip()
        if not value:
            raise ValueError("Le titre du ticket est obligatoire.")
        return value

    @validates("priority")
    def validate_priority(self, key, value):
        allowed = {"low", "medium", "high", "urgent"}
        if value not in allowed:
            raise ValueError(
                "Priorité invalide : low, medium, high ou urgent."
            )
        return value

    @validates("status")
    def validate_status(self, key, value):
        allowed = {
            "open",
            "in_progress",
            "resolved",
            "closed",
        }
        if value not in allowed:
            raise ValueError(
                "Statut invalide : open, in_progress, resolved ou closed."
            )
        return value
