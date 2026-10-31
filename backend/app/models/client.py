
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship, validates

from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    company = Column(String(150), nullable=True)
    phone = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, default="active")

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
        value = value.strip()
        if not value:
            raise ValueError("Le nom du client est obligatoire.")
        return value

    @validates("status")
    def validate_status(self, key, value):
        allowed = {"active", "inactive", "prospect"}
        if value not in allowed:
            raise ValueError(
                "Le statut doit être active, inactive ou prospect."
            )
        return value
