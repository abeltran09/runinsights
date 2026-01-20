from abc import abstractmethod
from sqlmodel import Session
from dependencies.pipeline_db import get_pipeline_session


class BaseIngestor:

    @abstractmethod
    def get_connections(self, db: Session) -> list:
        pass

    @abstractmethod
    def ingest(self, connection):
        pass

    def run(self):
        with get_pipeline_session() as db:
            connections = self.get_connections(db)
            for conn in connections:
                self.ingest(conn)