from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, BackgroundTasks
from sqlmodel import Session
from services.oauthmanager import OauthManager
from dependencies.strava_oauth import get_oauth_manager
from dependencies.db import create_db_engine, create_all_tables, get_session
from typing import Annotated
from models.user_models import StravaAthlete
from models.token_models import BearerToken
from services.strava_connect import get_strava_connection
from dependencies.ingestors import get_strava_ingestor
from pipelines.ingest.StravaIngestor import StravaIngestor
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = create_db_engine()
    create_all_tables(app.state.engine)
    print("Database engine created and tables initialized")

    yield

    app.state.engine.dispose()
    print("Database engine disposed")


app = FastAPI(lifespan=lifespan)


@app.get("/")
def hello_world():
    return {"Hello": "World"}


@app.get("/request-access")
def generate_authorization_url(oauth: Annotated[OauthManager, Depends(get_oauth_manager)]):
    return oauth.request_access()


@app.get("/oauth/callback")
def oauth_callback(request: Request,
                   oauth: Annotated[OauthManager, Depends(get_oauth_manager)],
                   db: Annotated[Session, Depends(get_session)]
                   ):

    code = request.query_params.get("code")

    if not code:
        raise HTTPException(400, "Missing authorization code")

    token_data = oauth.token_exchange(code)
    data = BearerToken(**token_data)
    athlete = StravaAthlete(**token_data['athlete'])

    user, connection = get_strava_connection(db, athlete)

    oauth.create_auth_token(db, connection, data)

    return {
        "message": "Authorization Successful"
    }


@app.post("/ingest")
def ingest_activities(background_tasks: BackgroundTasks,
                      ingestor: Annotated[StravaIngestor, Depends(get_strava_ingestor)]):
    # Ingestion can sleep for 15 min on rate limits, so run it outside the request
    background_tasks.add_task(ingestor.run)

    return {
        'message': "Ingestion started"
    }
