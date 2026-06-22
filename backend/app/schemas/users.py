from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.inventory import UserRole


class UserBootstrapCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    reason: str = Field(min_length=3)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=3, max_length=255)
    temporary_password: str = Field(min_length=10, max_length=128)
    role: UserRole
    reason: str = Field(min_length=3)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    reason: str = Field(min_length=3)

    @model_validator(mode="after")
    def require_change(self) -> "UserUpdate":
        if self.full_name is None and self.role is None and self.is_active is None:
            raise ValueError("Debe indicar al menos un cambio.")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime


class CurrentUserRead(UserRead):
    permissions: list[str]


class UserPasswordReset(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=128)
    reason: str = Field(min_length=3)
