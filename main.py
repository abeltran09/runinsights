from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from services.oauthmanager import OauthManager
from dependencies.strava_oauth import get_oauth_manager


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # nothing yet db will go here
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def hello_world():
    return {"Hello": "World"}


@app.get("/request-access")
def generate_authorization_url(oauth: OauthManager = Depends(get_oauth_manager)):
    return oauth.request_access()


@app.get("/oauth/callback")
def oauth_callback(request: Request, oauth: OauthManager = Depends(get_oauth_manager)):
    code = request.query_params['code']

    if not code:
        return {"error" : "Missing authorization code"}

    oauth.token_exchange(code)

    return {
        "message": "Authorization Successful",
        "Authorization_code": code
    }