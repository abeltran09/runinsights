from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException, Query
from sqlmodel import Session, select
from services.oauthmanager import OauthManager
from dependencies.strava_oauth import get_oauth_manager
from dependencies.db import create_db_engine, create_all_tables, get_session
from typing import Annotated
from models.user_models import User, StravaAthlete, UserId
from models.token_models import BearerToken
from services.user_service import create_user
from services.strava_connect import get_strava_connection
from dependencies.ingestors import get_strava_ingestor
from pipelines.ingest.StravaIngestor import StravaIngestor
from models.activities import Activities, ActivityStreams
from models.stravaconnection import StravaConnection
import requests
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation
from sqlalchemy import desc
from sqlalchemy.dialects.postgresql import insert

load_dotenv()


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

@app.get("/get-activities")
def ingest_activities(ingestor: Annotated[StravaIngestor, Depends(get_strava_ingestor)]):
    ingestor.run()

    return {
        'message': "Successful"
    }


@app.get("/get-token")
def get_access_token(db: Annotated[Session, Depends(get_session)],
                     oauth: Annotated[OauthManager, Depends(get_oauth_manager)],
                     connection_id: Annotated[int, Query()]
                     ):
    token = oauth.fetch_token(db, connection_id)

    return {
        'access_token': token.access_token
    }


@app.get("/test-func")
def get_access_token(db: Annotated[Session, Depends(get_session)]):

    activity_list = list(db.exec(
        select(Activities)
        .where(Activities.strava_connection_id == StravaConnection.id).limit(1)
    ).all())

    token = '5993d259a74845518847462ca6d3dc82b1c7f7b7'

    url = "https://www.strava.com/api/v3/activities/{activity_id}/streams"

    params = {
        'keys': 'time,distance,heartrate',
        'key_by_type': 'true'
    }

    headers = {
        'Authorization': f'Bearer {token}'
    }

    for activity in activity_list:
        stream_activity_resp = requests.get(
            url.format(activity_id=activity.strava_activity_id),
            params=params,
            headers=headers)

        stream_activity_resp.raise_for_status()

        streams = stream_activity_resp.json()

        time_data = streams.get("time", {}).get("data", [])
        distance_data = streams.get("distance", {}).get("data", [])
        hr_data = streams.get("heartrate", {}).get("data", [])

        processed_stream = []

        for i, t in enumerate(time_data):
            processed_stream.append(
                ActivityStreams(
                    strava_activity_id=activity.strava_activity_id,
                    time_sec=t,
                    distance_m=distance_data[i] if i < len(distance_data) else None,
                    heartrate_bpm=hr_data[i] if i < len(hr_data) else None
                )
            )
        try:
            db.add_all(processed_stream)
            db.commit()

        except IntegrityError as e:
            db.rollback()
            if isinstance(e.orig, UniqueViolation):
                continue
            else:
                raise


        return {
            'message':'successful'
        }

@app.get("/test-increment")
def get_access_token(db: Annotated[Session, Depends(get_session)]):
    latest_activity = db.exec(
        select(Activities.start_date)
        .where(Activities.strava_connection_id == StravaConnection.id)
        .order_by(desc(Activities.start_date))
    ).first()

    if not latest_activity:
        print(f"No existing activities for connection: {StravaConnection.id}")
        return {
            'status': 'skipped',
            'complete': False,
            'reason': 'no_baseline'
        }

    URL = 'https://www.strava.com/api/v3/activities'
    headers = {
        'Authorization': f'Bearer a8a640e2d8b3c07939684e91b339e4160de8ba84'
    }

    current_page = 1
    total_ingested = 0
    after_ts = int(latest_activity.timestamp()) - 1

    try:
        while True:

            params = {
                'after': after_ts,
                'per_page': 50,
                'page': current_page
            }

            activity_resp = requests.get(URL, params=params, headers=headers)

            activity_resp.raise_for_status()
            activities = activity_resp.json()

            if not activities:
                return {
                    'status': 'complete',
                    'completed': True,
                    'last_page': current_page - 1,
                    'ingested': total_ingested
                }

            print(f"Page {current_page}: fetched {len(activities)} activities")

            for activity in activities:
                print(
                    f"id={activity['id']} "
                    f"start_date={activity['start_date']} "
                    f"name={activity.get('name')}"
                )

            insert_stmt = insert(Activities).values(activities)
            update_insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["strava_activity_id"],
                set_={
                    "name": insert_stmt.excluded.name,
                    "distance": insert_stmt.excluded.distance,
                    "has_kudos": insert_stmt.excluded.has_kudos,
                    "kudos_count": insert_stmt.excluded.kudos_count
                }
            )

            total_ingested += len(activities)
            current_page += 1

    except Exception as e:
        return {
            'status': 'failed',
            'completed': False,
            'last_page': current_page,
            'error': str(e)
        }