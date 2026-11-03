"""Run Strava ingestion from the command line or a scheduler: python -m pipelines.run_ingest"""
from dotenv import load_dotenv
from dependencies.ingestors import get_strava_ingestor
import models  # noqa: F401  registers every table so foreign keys resolve outside the API
import logging


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    get_strava_ingestor().run()


if __name__ == "__main__":
    main()
