from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from enum import Enum


class PipelineStatus(Enum):
    STARTED = "started"
    RUNNING = "running"
    SKIPPED = "skipped"
    COMPLETE = "complete"
    FAILED = "failed"
    PAUSED = "paused_daily_limit"
    NOT_STARTED = "not_started"


class StravaConnection(SQLModel, table=True):
    id: int | None = Field(default_factory=None, primary_key=True)
    user_skey: int = Field(foreign_key="user.user_skey", nullable=False)
    strava_user_id: int = Field(nullable=False)

    # ingestion tracking
    last_activity_ingested_at: datetime = Field(nullable=True)
    backfill_status: PipelineStatus = Field(default=PipelineStatus.NOT_STARTED)
    initial_backfill_completed: bool = Field(default=False)

    # metadata
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime | None
    updated_at: datetime | None
    last_synced_at: datetime = Field(nullable=True)
    is_active: bool = Field(default=True)

    # stats
    total_activities_ingested: int = Field(default=0)
