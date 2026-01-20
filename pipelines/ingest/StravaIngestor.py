from pipelines.ingest.base import BaseIngestor
from models.user_models import User
from sqlmodel import select, Session
from dependencies.strava_oauth import get_oauth_manager
import requests
import urllib.parse


class StravaIngestor(BaseIngestor):


    def get_connections(self, db: Session) -> list:
        query = select(User).where(User.strava_connected == True)
        users = db.exec(query).all()
        return list(users)

    def ingest(self, db: Session):
        users = self.get_connections(db)
        for user in users:
            try:
                oauth = get_oauth_manager()
                token = oauth.fetch_token(db, user.strava_user_id)
                activities = self.fetch_activities(token.access_token)
            except Exception as e:
                print(f"Falied to ingest data from user {user.id}: {e}")

    def fetch_activities(self, token):
        """
        200 Successful request
        201 Your activity/etc. was successfully created
        401 Unauthorized
        403 Forbidden; you cannot access
        404 Not found; the requested asset does not exist, or you are not authorized to see it
        429 Too Many Requests; you have exceeded rate limits
        500 Strava is having issues, please check https://status.strava.com
        :param token:
        :return:
        """
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

            all_activities.extend(activities)
            params['page'] += 1

        return all_activities


    





