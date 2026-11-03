import urllib.parse
import requests
from models.token_models import BearerToken, StravaAuthToken, UserToken
from models.stravaconnection import StravaConnection
from sqlmodel import Session, select
from models.user_models import StravaAthlete
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta


class OauthManager:
    STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
    STRAVA_AUTH_V3_URL = "https://www.strava.com/api/v3/oauth/token"
    REFRESH_BUFFER = timedelta(hours=1)

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Missing required OAuth environment variables")


    def request_access(self) -> str:
        """Creates authorization url for a user

        args: none

        returns:
            string: generate authorization url
        """
        params = {'client_id':self.client_id,
                   "redirect_uri":self.redirect_uri,
                   "response_type":"code",
                   "approval_prompt":"force",
                   "scope":"read,activity:read_all"}

        return f"{self.STRAVA_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def token_exchange(self, auth_code):
        payload = {
            'client_id':self.client_id,
            'client_secret':self.client_secret,
            'code':auth_code,
            'grant_type':'authorization_code'
        }

        response = requests.post(self.STRAVA_AUTH_V3_URL, data=payload)
        response.raise_for_status()

        return response.json()

    def fetch_token(self, db: Session, connection_id: int):
        query = select(StravaAuthToken).where(StravaAuthToken.strava_connection_id == connection_id)
        token = db.exec(query).first()

        if not token:
            raise ValueError("This token does not exist")

        now = datetime.now(timezone.utc)
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            # Stored as UTC in a timezone-naive column
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now + self.REFRESH_BUFFER:
            refreshed = self.refresh_token(token)

            token.access_token = refreshed.access_token
            token.refresh_token = refreshed.refresh_token
            token.expires_at = refreshed.expires_at

            db.add(token)
            db.commit()
            db.refresh(token)

        return token

    def refresh_token(self, user_token: StravaAuthToken):
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': user_token.refresh_token
        }

        response = requests.post(self.STRAVA_AUTH_V3_URL, data=payload)
        response.raise_for_status()

        return UserToken(**response.json())

    def create_auth_token(self, db: Session, strava_connection: StravaConnection, data: BearerToken):
        """Saves the connection's token, replacing the existing one if the athlete re-authorizes."""
        query = select(StravaAuthToken).where(StravaAuthToken.strava_connection_id == strava_connection.id)
        token = db.exec(query).first()

        if token is None:
            token = StravaAuthToken(strava_connection_id=strava_connection.id)

        token.access_token = data.access_token
        token.token_type = data.token_type
        token.refresh_token = data.refresh_token
        token.expires_at = data.expires_at

        db.add(token)
        db.commit()
        db.refresh(token)
        return token
