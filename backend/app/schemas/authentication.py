from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.users import CurrentUserRead


class LoginCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class LoginRead(BaseModel):
    user: CurrentUserRead
    expires_at: datetime


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
    reason: str = Field(min_length=3)


class SetupStatusRead(BaseModel):
    needs_bootstrap: bool


class MessageRead(BaseModel):
    message: str
