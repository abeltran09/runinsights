import urllib.parse
class OauthManager:
    STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"

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

    def token_exchange(self, auth_code_url):
        pass

    def fetch_token(self):
        pass

    def refresh_token(self):
        pass