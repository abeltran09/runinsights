import urllib.parse
import requests
class OauthManager:
    STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
    STRAVA_AUTH_V3_URL = "https://www.strava.com/api/v3/oauth/token"

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
                   "redirect_uri":"http://localhost/exchange_token",
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

    def fetch_token(self):
        pass

    def refresh_token(self):
        pass