from sqlmodel import Field, SQLModel
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from models.user_models import StravaAthlete


class StravaAuthToken(SQLModel, table=True):
    strava_user_id: int | None = Field(default=None, primary_key=True)
    token_type: str
    access_token: str
    refresh_token: str
    expires_at: datetime


class BearerToken(BaseModel):
    token_type: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    expires_in: int
    athlete: StravaAthlete

    @field_validator("expires_at", mode="before")
    @classmethod
    def parse_epoch(cls, v):
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return v


class UserToken(BaseModel):
    token_type: str
    access_token: str
    refresh_token: str
    expires_at: datetime






