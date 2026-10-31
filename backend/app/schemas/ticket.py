
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TicketPriority = Literal["low", "medium", "high", "urgent"]

TicketStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]


class TicketBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5)
    priority: TicketPriority = "medium"
    status: TicketStatus = "open"
    client_id: int = Field(gt=0)
    assigned_to: str | None = Field(default=None, max_length=120)


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=5)
    priority: TicketPriority | None = None
    status: TicketStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=120)


class TicketResponse(TicketBase):
    id: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
