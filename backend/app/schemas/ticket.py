from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


TicketPriority = Literal["low", "medium", "high", "urgent"]

TicketStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]


def normalize_utc(value: datetime | None) -> datetime | None:
    """Interprète les dates naïves comme UTC et convertit les dates zonées."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class TicketBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=10_000)
    priority: TicketPriority = "medium"
    status: TicketStatus = "open"
    client_id: int = Field(gt=0)
    assigned_to: str | None = Field(default=None, max_length=120)


class TicketCreate(TicketBase):
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value):
        return normalize_utc(value)


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=5, max_length=10_000)
    priority: TicketPriority | None = None
    status: TicketStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value):
        return normalize_utc(value)


class TicketResponse(TicketBase):
    id: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    due_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value):
        """Normalise en UTC les dates récupérées depuis la base."""
        return normalize_utc(value)

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Indique si le ticket est en retard et encore actif."""
        if self.due_at is None:
            return False

        if self.status in {"resolved", "closed"}:
            return False

        due_at = normalize_utc(self.due_at)
        return due_at < datetime.now(timezone.utc)