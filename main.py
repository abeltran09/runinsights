from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI
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
