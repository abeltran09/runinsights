from pipelines.ingest.base import BaseIngestor
from models.user_models import User
from models.activities import Activities, validate_raw_data
from models.stravaconnection import StravaConnection
from sqlmodel import select, Session
from sqlalchemy import desc
from dependencies.strava_oauth import get_oauth_manager
import requests
import urllib.parse
from datetime import datetime, timezone
from pydantic import ValidationError
from dependencies.strava_oauth import get_strava_rate_limiter
import time


class StravaIngestor(BaseIngestor):

    def __init__(self, oauth_manager=None, strava_rate_limiter=None, max_retries: int = 3):
        super().__init__(max_retries)
        self.oauth_manager = oauth_manager or get_oauth_manager()
        self.strava_rate_limiter = strava_rate_limiter or get_strava_rate_limiter()

    def get_connections(self, db: Session) -> list[StravaConnection]:
        self.logger.info("Retrieving all Strava Connection...")
        query = select(StravaConnection)
        users = db.exec(query).all()
        return list(users)

    def ingest(self, db: Session):
        strava_connections = self.get_connections(db)

        for connection in strava_connections:
            try:
                self._ingest_connection(db, connection)
            except Exception as e:
                self.logger.error(f"Failed to ingest data from user {connection.id}: {e}", exc_info=True)

    def _ingest_connection(self, db: Session, connection: StravaConnection):
        self.logger.info(f"Starting ingestion for connection {connection.id}")

        token = self.oauth_manager.fetch_token(db, connection.id)
        activities, is_backfill = self._fetch_activities(db, token.access_token, connection)

        if activities:
            self._store_activities(db, activities, connection, is_backfill)
            self.logger.info(f"Successfully Ingested {len(activities)} for connection {connection.id}")

        else:
            self.logger.info(f"No new activities for connection: {connection.id}")


    def _fetch_activities(self, db: Session, token: str, connection: StravaConnection):
        """
        200 Successful request
        201 Your activity/etc. was successfully created
        401 Unauthorized
        403 Forbidden; you cannot access
        404 Not found; the requested asset does not exist, or you are not authorized to see it
        429 Too Many Requests; you have exceeded rate limits
        500 Strava is having issues, please check https://status.strava.com
        :param db:
        :param connection:
        :param token:
        :return:
        """
        if not connection.initial_backfill_completed:
            self.logger.info(f"Performing initial backfill for connection: {connection.id}")
            return self.initial_backfill(db, token, connection), True

        else:
            self.logger.info(f"Performing incremental sync for connection: {connection.id}")
            return self.incremental_ingest(db, token, connection), False

    def _store_activities(self,
                         db: Session, activities: list[dict],
                         connection: StravaConnection,
                         mark_backfill_complete: bool = False):

        new_activities = []

        for activity in activities:
            try:
                raw_activity = validate_raw_data(activity)

                new_activities.append(
                    Activities(
                        strava_connection_id=connection.id,
                        strava_activity_id=raw_activity.id,
                        distance=raw_activity.distance,
                        moving_time=raw_activity.moving_time,
                        sport_type=raw_activity.sport_type,
                        device_name=raw_activity.device_name,
                        start_date=raw_activity.start_date,
                        timezone=raw_activity.timezone,
                        average_speed=raw_activity.average_speed,
                        max_speed=raw_activity.max_speed,
                        has_heartrate=raw_activity.has_heartrate,
                        average_heartrate=raw_activity.average_heartrate,
                        max_heart_rate=raw_activity.max_heartrate
                    )
                )
            except ValidationError as e:
                self.logger.error(f"Failed to validate activity for connection: {connection.id} - {e}")

        if new_activities:
            db.add_all(new_activities)

        if mark_backfill_complete:
            connection.initial_backfill_completed = True

        connection.total_activities_ingested += len(new_activities)
        connection.last_activity_ingested_at = datetime.utcnow()
        connection.last_synced_at = datetime.utcnow()

        db.add(connection)

        db.commit()
        return True

    def initial_backfill(self, db: Session, token: str, connection: StravaConnection):
        URL = 'https://www.strava.com/api/v3/activities'
        params = {
            'page': 1,
            'per_page': 200
        }
        headers = {
            'Authorization': f'Bearer {token}'
        }
        all_activities = []

        while True:
            activity_resp = requests.get(URL, params=params, headers=headers)
            activity_resp.raise_for_status()

            activities = activity_resp.json()

            if not activities:
                break

            self.strava_rate_limiter.update_from_headers(activity_resp.headers)

            if self.strava_rate_limiter.should_throttle():
                time.sleep(15*60)

            all_activities.extend(activities)
            params['page'] += 1

        return all_activities

    def incremental_ingest(self, db: Session, token: str, connection: StravaConnection):
        print("HERE")
        latest_activity = db.exec(
            select(Activities.start_date)
            .where(Activities.strava_connection_id == connection.id)
            .order_by(Activities.start_date.desc())
        ).first()

        URL = 'https://www.strava.com/api/v3/activities'
        params = {
            'after': int(latest_activity.timestamp()) if latest_activity else 0,
            'per_page': 200,
            'page': 1
        }
        headers = {
            'Authorization': f'Bearer {token}'
        }
        all_activities = []

        while True:
            activity_resp = requests.get(URL, params=params, headers=headers)
            activity_resp.raise_for_status()
            activities = activity_resp.json()

            if not activities:
                break

            all_activities.extend(activities)
            params['page'] += 1

        return all_activities

