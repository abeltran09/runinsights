from contextlib import contextmanager
from sqlmodel import create_engine, Session
from core.config import get_db_config

db_url = get_db_config()
engine = create_engine(db_url)


@contextmanager
def get_pipeline_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
