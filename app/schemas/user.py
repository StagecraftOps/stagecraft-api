import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    github_id: int
    login: str
    name: str | None = None
    avatar_url: str
    email: str | None = None

class UserCreate(UserBase):
    access_token_encrypted: str

class UserUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    access_token_encrypted: str | None = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    login: str
    name: str | None = None
    avatar_url: str
    email: str | None = None
