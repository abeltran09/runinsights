from core.config import get_db_config
from sqlmodel import create_engine, Session, SQLModel
from fastapi import Request


def create_db_engine():
    db_url = get_db_config()
    engine = create_engine(db_url, echo=True)
    return engine


def get_session(request: Request):
    db = Session(request.app.state.engine)
    try:
        yield db
    finally:
        db.close()


def create_all_tables(engine):
    import models
    SQLModel.metadata.create_all(engine)
