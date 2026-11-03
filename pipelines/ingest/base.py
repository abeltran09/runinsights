from abc import abstractmethod
from sqlmodel import Session
from dependencies.pipeline_db import get_pipeline_session
import logging

logger = logging.getLogger(__name__)


class BaseIngestor:
    """Base class for data ingestors"""

    def __init__(self, max_retries: int = 3):
        self.max_retries =  max_retries
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_connections(self, db: Session) -> list:
        """Get all connections that need to be ingested"""
        pass

    @abstractmethod
    def ingest(self, db: Session):
        """Main ingestion logic"""
        pass

    def run(self):
        """Run ingestion process"""
        try:
            with get_pipeline_session() as db:
                self.ingest(db)
        except Exception as e:
            self.logger.error(f"Ingestion failed: {e}", exc_info=True)
            raise
