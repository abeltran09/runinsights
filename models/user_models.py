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
    city: str | None
    state: str | None
    country: str | None
    sex: SexEnum | None
    weight: float | None
    height: float | None
    created_via: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StravaAthlete(BaseModel):
    # Strava returns null for, or leaves out, these when the athlete hasn't filled out their profile,
    # so every optional field needs a default (in Pydantic v2 `X | None` alone is still required)
    id: int
    username: str | None = None
    resource_state: int | None = None
    firstname: str
    lastname: str
    bio: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    sex: SexEnum | None = None
    premium: bool = False
    summit: bool = False
    created_at: datetime
    updated_at: datetime
    badge_type_id: int | None = None
    weight: float | None = None
    profile_medium: str | None = None
    profile: str | None = None
    friend: int | None = None
    follower: int | None = None


class UserId(BaseModel):
    id: int

