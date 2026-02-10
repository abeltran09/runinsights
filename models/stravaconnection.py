from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel

class Progress(str, Enum):
    not_started: str = "not_started",
    in_progress: str = "in_progress",
    complete: str = "complete"
    paused: str = "paused_daily_limit"




class StravaConnection(SQLModel, table=True):
    id: int | None = Field(default_factory=None, primary_key=True)
    user_skey: int = Field(foreign_key="user.user_skey", nullable=False)
    strava_user_id: int = Field(nullable=False)

    # ingestion tracking
    last_activity_ingested_at: datetime = Field(nullable=True)
    backfill_status: Progress = Field(default='not_started')
    initial_backfill_completed: bool = Field(default=False)
    last_page: int = Field(default=1)

    # metadata
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime | None
    updated_at: datetime | None
    last_synced_at: datetime = Field(nullable=True)
    is_active: bool = Field(default=True)

    # stats
    total_activities_ingested: int = Field(default=0)
