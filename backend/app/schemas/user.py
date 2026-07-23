"""User management schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    display_name: str
    role: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=4, max_length=256)
    role: str = Field(default="viewer")
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = None
    is_active: bool | None = None


class ChangePasswordRequest(BaseModel):
    password: str = Field(min_length=4, max_length=256)
