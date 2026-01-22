from sqlmodel import Field, SQLModel
from pydantic import BaseModel, ValidationError
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column


class Activities(SQLModel, table=True):
    id: int | None = Field(default=None, nullable=False, primary_key=True)
    strava_connection_id: int = Field(foreign_key='stravaconnection.id', nullable=False)
    strava_activity_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
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


class RawActivitiesIn(BaseModel):
    id: int
    distance: float
    moving_time: int
    sport_type: str
    device_name: str | None = None
    start_date: datetime
    timezone: str
    average_speed: float
    max_speed: float
    has_heartrate: bool
    average_heartrate: float | None = None
    max_heart_rate: float | None = None


def validate_raw_data(data: dict):
    try:
        return RawActivitiesIn.model_validate(data)
    except ValidationError as e:
        print("Error Validating data:", e)
        return None
