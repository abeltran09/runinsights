from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel


class SexEnum(str, Enum):
    M = 'M'
    F = 'F'


class User(SQLModel, table=True):
    user_skey: int | None = Field(default=None, primary_key=True)
    firstname: str
    lastname: str
    city: str
    state: str
    country: str
    sex: SexEnum = Field(nullable=False)
    weight: float | None
    height: float | None
    created_via: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StravaAthlete(BaseModel):
    id: int
    username: str | None
    resource_state: int | None
    firstname: str
    lastname: str
    bio: str | None
    city: str
    state: str
    country: str
    sex: SexEnum
    premium: bool
    summit: bool
    created_at: datetime
    updated_at: datetime
    badge_type_id: int | None
    weight: float | None
    profile_medium: str | None
    profile: str | None
    friend: int | None
    follower: int | None


class UserId(BaseModel):
    id: int

