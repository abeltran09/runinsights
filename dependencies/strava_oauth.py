from core.config import get_oauth_config
from services.oauthmanager import OauthManager
from services.strava_rate_limiter import StravaRateLimiter


def get_oauth_manager():
    config = get_oauth_config()
    return OauthManager(**config)


def get_strava_rate_limiter():
    return StravaRateLimiter()
