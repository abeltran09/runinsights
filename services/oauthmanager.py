import urllib.parse
import requests
from models.token_models import BearerToken, StravaAuthToken, UserToken
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
                   "scope":"read"}

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

    def fetch_token(self, db: Session, user: StravaAthlete):
        query = select(StravaAuthToken).where(StravaAuthToken.strava_user_id == user.id)
        token = db.exec(query).first()

        if not token:
            raise ValueError("This token does not exist")

        now = datetime.now(timezone.utc)

        if token.expires_at > now or token.expires_at - self.REFRESH_BUFFER > now:
            return token

        refreshed_token = self.refresh_token(token)

        token.refresh_token = refreshed_token.refresh_token
        token.expires_at = refreshed_token.expires_at

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

    def create_auth_token(self, db: Session, data: BearerToken):
        token = StravaAuthToken(
            strava_user_id=data.athlete.id,
            access_token=data.access_token,
            token_type=data.token_type,
            refresh_token=data.refresh_token,
            expires_at=data.expires_at,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token
