from core.config import get_oauth_config
from services.oauthmanager import OauthManager
from sqlmodel import Session, select
from models.token_models import StravaAuthToken


def get_oauth_manager():
    config = get_oauth_config()
    return OauthManager(**config)

