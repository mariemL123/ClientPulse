
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


ClientStatus = Literal["active", "inactive", "prospect"]


class ClientBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    status: ClientStatus = "active"


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    company: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    status: ClientStatus | None = None


class ClientResponse(ClientBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
