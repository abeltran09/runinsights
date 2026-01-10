from core.config import get_oauth_config
from services.oauthmanager import OauthManager

def get_oauth_manager():
    config = get_oauth_config()
    return OauthManager(**config)