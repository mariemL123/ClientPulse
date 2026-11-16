from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TicketAttachment(Base):
    """Métadonnées d'un fichier joint à un ticket."""

    __tablename__ = "ticket_attachments"

    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0",
            name="ck_ticket_attachments_positive_size",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Nom présenté à l'utilisateur, jamais utilisé comme chemin disque.
    original_filename = Column(String(255), nullable=False)

    # Clé interne générée par le serveur, indépendante du nom original.
    storage_key = Column(String(100), nullable=False, unique=True, index=True)

    content_type = Column(String(100), nullable=False)

    size_bytes = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ticket = relationship(
        "Ticket",
        back_populates="attachments",
    )