from pipelines.ingest.base import BaseIngestor
from models.user_models import User
from models.activities import Activities, validate_raw_data, ActivityStreams, RawActivityStreamIn
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
from sqlalchemy.dialects.postgresql import insert

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
        fetch_status = self._fetch_activities(db, token.access_token, connection)

        if fetch_status["completed"]:
            self.logger.info("Successful ingest")

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
            return self.initial_backfill(db, token, connection)

        else:
            self.logger.info(f"Performing incremental sync for connection: {connection.id}")
            return self.incremental_ingest(db, token, connection)

    def _store_activities(self, db: Session, activities: list[dict], connection: StravaConnection):
        activities_to_insert = []
        for activity in activities:
            try:
                raw_activity = validate_raw_data(activity)

                activities_to_insert.append({
                    'strava_connection_id': connection.id,
                    'strava_activity_id': raw_activity.id,
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
                    'max_heart_rate': raw_activity.max_heartrate
                })
            except ValidationError as e:
                self.logger.error(f"Failed to validate activity for connection: {connection.id} - {e}")

        if activities_to_insert:
            stmt = insert(Activities).values(activities_to_insert)
            stmt = stmt.on_conflict_do_nothing(index_elements=['strava_activity_id'])
            db.execute(stmt)

        connection.total_activities_ingested += len(activities_to_insert)
        connection.last_activity_ingested_at = datetime.utcnow()
        connection.last_synced_at = datetime.utcnow()

        db.add(connection)
        db.commit()
        return True

    def _ingest_activity_streams(self, db: Session, token: str, connection: StravaConnection):
        activity_list = list(db.exec(
            select(Activities)
            .where(Activities.strava_connection_id == connection.id).limit(1)
        ).all())

        url = "https://www.strava.com/api/v3/activities/{activity_id}/streams"

        params = {
            'keys': 'time,distance,heartrate',
            'key_by_type': 'true'
        }

        headers = {
            'Authorization': f'Bearer {token}'
        }

        for activity in activity_list:
            stream_activity_resp = requests.get(
                url.format(activity_id=activity.strava_activity_id),
                params=params,
                headers=headers)

            stream_activity_resp.raise_for_status()

            streams = stream_activity_resp.json()

            time_data = streams.get("time", {}).get("data", [])
            distance_data = streams.get("distance", {}).get("data", [])
            hr_data = streams.get("heartrate", {}).get("data", [])

            processed_stream = []

            for i, t in enumerate(time_data):
                processed_stream.append(
                    ActivityStreams(
                        strava_activity_id=activity.strava_activity_id,
                        time_sec=t,
                        distance_m=distance_data[i] if i < len(distance_data) else None,
                        heartrate_bpm=hr_data[i] if i < len(distance_data) else None
                    )
                )

            db.add(processed_stream)
            db.commit()

    def initial_backfill(self, db: Session, token: str, connection: StravaConnection):
        URL = 'https://www.strava.com/api/v3/activities'
        headers = {
            'Authorization': f'Bearer {token}'
        }

        current_page = connection.last_page if connection.last_page and connection.last_page != 0 else 1

        try:
            while True:
                if self.strava_rate_limiter.should_throttle():
                    if self.strava_rate_limiter.is_daily_limit_hit():
                        self._checkpoint_backfill(db, connection, current_page, 'paused_daily_limit')
                        raise Exception(
                            f"Daily limit reached at page {current_page}"
                            f"Usage: {self.strava_rate_limiter.read_daily_usage/self.strava_rate_limiter.read_daily_limit}"
                        )
                    else:
                        self.logger.info("15 min rate limit approaching sleep for 15 minutes")
                        time.sleep(15*60)

                params = {
                    'page': current_page,
                    'per_page': 50
                }

                activity_resp = requests.get(URL, params=params, headers=headers)

                self.strava_rate_limiter.update_from_headers(activity_resp.headers)

                if activity_resp.status_code == 429:
                    self.logger.warning(f"Got 429 response. Usage: {self.strava_rate_limiter.read_daily_usage}")

                    if self.strava_rate_limiter.is_daily_limit_hit():
                        self._checkpoint_backfill(db, connection, current_page, "paused_daily_limit")
                        raise Exception(f"Daily limit exceeded at page {current_page}")
                    else:
                        self.logger.info("15 min rate limit approaching sleep for 15 minutes")
                        time.sleep(15 * 60)
                        continue

                activity_resp.raise_for_status()
                activities = activity_resp.json()

                if not activities:
                    connection.backfill_status = "complete"
                    connection.initial_backfill_completed = True
                    db.add(connection)
                    db.commit()
                    self.logger.info("Backfill is complete")
                    return {
                        'status': 'complete',
                        'completed': True,
                        'last_page': current_page
                    }


                self.logger.info(f"Backfilling connection: {connection.id}, on page: {params['page']} backfill is in progress")
                self._store_activities(db, activities, connection)
                current_page += 1
                connection.last_page = current_page
                connection.backfill_status = "in_progress"

        except Exception as e:
            self.logger.error(f"Backfill failed: {e}")
            return {
                'status': 'failed',
                'completed': False,
                'last_page': current_page,
                'error': str(e)
            }



    def _checkpoint_backfill(self, db:Session, connection: StravaConnection, page: int, status: str):
        connection.last_page = page
        connection.backfill_status = status

        db.add(connection)
        db.commit()
        self.logger.info(f"Checkpointed connection {connection.id} at page {page}, status: {status}")

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

