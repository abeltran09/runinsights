import os


def get_oauth_config():
    return {
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "redirect_uri": os.environ["REDIRECT_URL"],
    }


def get_db_config():
    return {
        "db_url": os.environ["DB_URL"]
    }