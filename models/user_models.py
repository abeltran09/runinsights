from sqlmodel import Field, SQLModel
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class SexEnum(str, Enum):
    M = 'M'
    F = 'F'


class User(SQLModel, table=True):
    user_skey: int | None = Field(default=None, primary_key=True)
    strava_user_id: int = Field(nullable=False)
    firstname: str
    lastname: str
    city: str
    state: str
    country: str
    sex: SexEnum = Field(nullable=False)
    weight: float | None
    height: float | None
    strava_created_at: datetime
    strava_updated_at: datetime


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



class UserRead(BaseModel):
    strava_user_id: str
    firstname: str
    lastname: str

class UserId(BaseModel):
    id: str

