from contextlib import contextmanager
from sqlmodel import create_engine, Session
from core.config import get_db_config

engine = None

def get_engine():
    global engine
    if engine is None:
        db_url = get_db_config()
        engine = create_engine(db_url)
    return engine


@contextmanager
def get_pipeline_session():
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()
