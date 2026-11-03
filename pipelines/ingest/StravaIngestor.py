from pipelines.ingest.base import BaseIngestor
from models.activities import Activities, validate_raw_data, ActivityStreams
from models.stravaconnection import StravaConnection, PipelineStatus
from sqlmodel import select, Session
from sqlalchemy import func
from dependencies.strava_oauth import get_oauth_manager
import requests
from datetime import datetime, timezone, timedelta
from dependencies.strava_oauth import get_strava_rate_limiter
import time
from sqlalchemy.dialects.postgresql import insert


def to_epoch(dt: datetime) -> int:
    """Postgres hands back naive datetimes that are really UTC; treat them that way."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class StravaIngestor(BaseIngestor):
    ACTIVITIES_URL = 'https://www.strava.com/api/v3/athlete/activities'
    STREAMS_URL = 'https://www.strava.com/api/v3/activities/{activity_id}/streams'
    PER_PAGE = 200  # Strava's max
    REQUEST_TIMEOUT = 30
    RATE_LIMIT_SLEEP = 15 * 60
    # Re-check a few days back so activities synced late (older start_date) are not missed
    INCREMENTAL_LOOKBACK = timedelta(days=3)

    def __init__(self, oauth_manager=None, strava_rate_limiter=None, max_retries: int = 3):
        super().__init__(max_retries)
        self.oauth_manager = oauth_manager or get_oauth_manager()
        self.strava_rate_limiter = strava_rate_limiter or get_strava_rate_limiter()

    def get_connections(self, db: Session) -> list[StravaConnection]:
        self.logger.info("Retrieving all Strava Connection...")
        query = select(StravaConnection).where(StravaConnection.is_active)
        return list(db.exec(query).all())

    def ingest(self, db: Session):
        strava_connections = self.get_connections(db)

        for connection in strava_connections:
            try:
                self._ingest_connection(db, connection)
            except Exception as e:
                db.rollback()
                self.logger.error(f"Failed to ingest data from user {connection.id}: {e}", exc_info=True)

    def _ingest_connection(self, db: Session, connection: StravaConnection):
        self.logger.info(f"Starting ingestion for connection {connection.id}")

        token = self.oauth_manager.fetch_token(db, connection.id)
        result = self._fetch_activities(db, token.access_token, connection)

        if result['status'] == PipelineStatus.COMPLETE:
            self.logger.info(f"Connection {connection.id}: ingested {result['ingested']} activities")
        elif result['status'] == PipelineStatus.PAUSED:
            self.logger.warning(
                f"Connection {connection.id}: paused on Strava daily limit after {result['ingested']} activities"
            )
        else:
            self.logger.error(f"Connection {connection.id}: ingestion failed - {result.get('error')}")

    def _fetch_activities(self, db: Session, token: str, connection: StravaConnection) -> dict:
        if not connection.initial_backfill_completed:
            self.logger.info(f"Performing initial backfill for connection: {connection.id}")
            return self.initial_backfill(db, token, connection)

        self.logger.info(f"Performing incremental sync for connection: {connection.id}")
        return self.incremental_ingest(db, token, connection)

    def _strava_get(self, url: str, token: str, params: dict) -> requests.Response | None:
        """
        GET a Strava endpoint while respecting rate limits.
        Sleeps through the 15 min limit; returns None once the daily limit is reached.
        Raises for any non-429 error status (401, 403, 404, 5xx).
        """
        headers = {'Authorization': f'Bearer {token}'}

        while True:
            if self.strava_rate_limiter.is_daily_limit_hit():
                return None
            if self.strava_rate_limiter.should_throttle():
                self.logger.info("15 min rate limit approaching, sleeping for 15 minutes")
                self._sleep_out_rate_limit()

            resp = requests.get(url, params=params, headers=headers, timeout=self.REQUEST_TIMEOUT)
            self.strava_rate_limiter.update_from_headers(resp.headers)

            if resp.status_code == 429:
                self.logger.warning(f"Got 429 response. Daily usage: {self.strava_rate_limiter.read_daily_usage}")
                if self.strava_rate_limiter.is_daily_limit_hit():
                    return None
                self.logger.info("15 min rate limit hit, sleeping for 15 minutes")
                self._sleep_out_rate_limit()
                continue

            if not resp.ok:
                # Strava explains 401/403s in the body (e.g. missing scope), which raise_for_status drops
                self.logger.error(f"Strava returned {resp.status_code} for {url}: {resp.text}")
            resp.raise_for_status()
            return resp

    def _sleep_out_rate_limit(self):
        time.sleep(self.RATE_LIMIT_SLEEP)
        self.strava_rate_limiter.reset_15_min_window()

    def _store_activities(self, db: Session, activities: list[dict], connection: StravaConnection) -> int:
        activities_to_insert = []
        for activity in activities:
            raw_activity = validate_raw_data(activity)
            if raw_activity is None:
                self.logger.error(
                    f"Skipping activity {activity.get('id')} for connection {connection.id}: failed validation"
                )
                continue

            activities_to_insert.append({
                'strava_connection_id': connection.id,
                'strava_activity_id': raw_activity.id,
                'name': raw_activity.name,
                'distance': raw_activity.distance,
                'moving_time': raw_activity.moving_time,
                'sport_type': raw_activity.sport_type,
                'device_name': raw_activity.device_name,
                'start_date': raw_activity.start_date,
                'timezone': raw_activity.timezone,
                'average_speed': raw_activity.average_speed,
                'max_speed': raw_activity.max_speed,
                'has_heartrate': raw_activity.has_heartrate,
                'average_heartrate': raw_activity.average_heartrate,
                'max_heart_rate': raw_activity.max_heartrate,
                'has_kudos': raw_activity.has_kudos,
                'kudos_count': raw_activity.kudos_count
            })

        if activities_to_insert:
            insert_stmt = insert(Activities).values(activities_to_insert)
            update_insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["strava_activity_id"],
                set_={
                    "name": insert_stmt.excluded.name,
                    "distance": insert_stmt.excluded.distance,
                    "has_kudos": insert_stmt.excluded.has_kudos,
                    "kudos_count": insert_stmt.excluded.kudos_count
                }
            )
            db.execute(update_insert_stmt)

        self._update_connection(db, connection)
        return len(activities_to_insert)

    def _update_connection(self, db: Session, connection: StravaConnection):
        # Count from the table so re-fetched (upserted) activities are never double counted
        connection.total_activities_ingested = db.exec(
            select(func.count()).select_from(Activities).where(Activities.strava_connection_id == connection.id)
        ).one()
        now = datetime.now(timezone.utc)
        connection.last_activity_ingested_at = now
        connection.last_synced_at = now
        db.add(connection)
        db.commit()

    def _ingest_activity_streams(self, db: Session, token: str, connection: StravaConnection):
        """Fetch per-second streams for activities that do not have any stored yet. Not wired into ingest() yet."""
        has_streams = select(ActivityStreams.strava_activity_id).where(
            ActivityStreams.strava_activity_id == Activities.strava_activity_id
        ).exists()

        activity_list = list(db.exec(
            select(Activities)
            .where(Activities.strava_connection_id == connection.id)
            .where(~has_streams)
        ).all())

        params = {
            'keys': 'time,distance,heartrate',
            'key_by_type': 'true'
        }

        for activity in activity_list:
            resp = self._strava_get(
                self.STREAMS_URL.format(activity_id=activity.strava_activity_id), token, params
            )
            if resp is None:
                self.logger.warning(f"Daily limit reached while fetching streams for connection {connection.id}")
                return

            streams = resp.json()
            time_data = streams.get("time", {}).get("data", [])
            distance_data = streams.get("distance", {}).get("data", [])
            hr_data = streams.get("heartrate", {}).get("data", [])

            processed_stream = [
                {
                    'strava_activity_id': activity.strava_activity_id,
                    'time_sec': t,
                    'distance_m': distance_data[i] if i < len(distance_data) else None,
                    'heartrate_bpm': hr_data[i] if i < len(hr_data) else None
                }
                for i, t in enumerate(time_data)
            ]

            if processed_stream:
                db.execute(insert(ActivityStreams).values(processed_stream).on_conflict_do_nothing(
                    index_elements=["strava_activity_id", "time_sec"]
                ))
                db.commit()

    def initial_backfill(self, db: Session, token: str, connection: StravaConnection) -> dict:
        """
        Walks backwards through history using `before` as a cursor (Strava returns newest first).
        If a previous run paused or failed, resumes from the oldest activity already stored.
        """
        oldest = db.exec(
            select(func.min(Activities.start_date)).where(Activities.strava_connection_id == connection.id)
        ).one()
        before_ts = to_epoch(oldest) if oldest else None
        if before_ts:
            self.logger.info(f"Resuming backfill for connection {connection.id} before {oldest}")

        self._checkpoint_backfill(db, connection, PipelineStatus.RUNNING)
        total_ingested = 0

        try:
            while True:
                params = {'per_page': self.PER_PAGE}
                if before_ts:
                    params['before'] = before_ts

                resp = self._strava_get(self.ACTIVITIES_URL, token, params)
                if resp is None:
                    self._checkpoint_backfill(db, connection, PipelineStatus.PAUSED)
                    return {'status': PipelineStatus.PAUSED, 'completed': False, 'ingested': total_ingested}

                activities = resp.json()

                if not activities:
                    connection.backfill_status = PipelineStatus.COMPLETE
                    connection.initial_backfill_completed = True
                    db.add(connection)
                    db.commit()
                    self.logger.info(
                        f"Backfill complete for connection {connection.id}. Activities ingested: {total_ingested}"
                    )
                    return {'status': PipelineStatus.COMPLETE, 'completed': True, 'ingested': total_ingested}

                self.logger.info(f"Backfilling connection {connection.id}: fetched {len(activities)} activities")
                total_ingested += self._store_activities(db, activities, connection)
                before_ts = min(to_epoch(datetime.fromisoformat(a['start_date'])) for a in activities)

        except Exception as e:
            db.rollback()
            self.logger.error(f"Backfill failed for connection {connection.id}: {e}", exc_info=True)
            self._checkpoint_backfill(db, connection, PipelineStatus.FAILED)
            return {'status': PipelineStatus.FAILED, 'completed': False, 'ingested': total_ingested, 'error': str(e)}

    def _checkpoint_backfill(self, db: Session, connection: StravaConnection, status: PipelineStatus):
        connection.backfill_status = status
        db.add(connection)
        db.commit()
        self.logger.info(f"Connection {connection.id} backfill status: {status.value}")

    def incremental_ingest(self, db: Session, token: str, connection: StravaConnection) -> dict:
        latest = db.exec(
            select(func.max(Activities.start_date)).where(Activities.strava_connection_id == connection.id)
        ).one()

        # No activities yet (athlete had none at backfill time): fetch everything
        after_ts = to_epoch(latest - self.INCREMENTAL_LOOKBACK) if latest else 0
        current_page = 1
        total_ingested = 0

        try:
            while True:
                params = {
                    'after': after_ts,
                    'per_page': self.PER_PAGE,
                    'page': current_page
                }

                resp = self._strava_get(self.ACTIVITIES_URL, token, params)
                if resp is None:
                    self.logger.warning(f"Daily limit hit before page {current_page}")
                    return {'status': PipelineStatus.PAUSED, 'completed': False, 'ingested': total_ingested}

                activities = resp.json()

                if not activities:
                    self._update_connection(db, connection)
                    self.logger.info(f"Incremental sync for connection {connection.id} complete")
                    return {'status': PipelineStatus.COMPLETE, 'completed': True, 'ingested': total_ingested}

                self.logger.info(f"Syncing connection {connection.id}, page {current_page}")
                total_ingested += self._store_activities(db, activities, connection)
                current_page += 1

        except Exception as e:
            db.rollback()
            self.logger.error(f"Incremental sync failed for connection {connection.id}: {e}", exc_info=True)
            return {'status': PipelineStatus.FAILED, 'completed': False, 'ingested': total_ingested, 'error': str(e)}
