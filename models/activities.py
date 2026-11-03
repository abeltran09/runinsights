from sqlmodel import Field, SQLModel
from pydantic import BaseModel, ValidationError
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, ForeignKey, UniqueConstraint


class Activities(SQLModel, table=True):
    id: int | None = Field(default=None, nullable=False, primary_key=True)
    strava_connection_id: int = Field(foreign_key='stravaconnection.id', nullable=False)
    strava_activity_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    name: str = Field(nullable=True)
    distance: float = Field(nullable=True)
    moving_time: int = Field(nullable=True)
    sport_type: str = Field(nullable=True)
    device_name: str = Field(nullable=True)
    start_date: datetime = Field(nullable=True)
    timezone: str = Field(nullable=True)
    average_speed: float = Field(nullable=True)
    max_speed: float = Field(nullable=True)
    has_heartrate: bool = Field(nullable=True)
    average_heartrate: float = Field(nullable=True)
    max_heart_rate: float = Field(nullable=True)
    has_kudos: bool = Field(nullable=True)
    kudos_count: int = Field(nullable=True)


class ActivityStreams(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('strava_activity_id', 'time_sec'),)

    id: int | None = Field(default=None, nullable=False, primary_key=True)
    strava_activity_id: int = Field(sa_column=Column(BigInteger, ForeignKey('activities.strava_activity_id'), nullable=False))
    time_sec: int = Field(nullable=False)
    distance_m: float | None
    heartrate_bpm: int | None


class RawActivityStreamIn(BaseModel):
    stream_type: str
    data: list
    stream_size: int


class RawActivitiesIn(BaseModel):
    id: int
    distance: float
    name: str | None
    moving_time: int
    sport_type: str
    device_name: str | None = None
    start_date: datetime
    timezone: str
    average_speed: float
    max_speed: float
    has_heartrate: bool
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    has_kudos: bool | None
    kudos_count: int | None


def validate_raw_data(data: dict):
    try:
        return RawActivitiesIn.model_validate(data)
    except ValidationError as e:
        print("Error Validating data:", e)
        return None
