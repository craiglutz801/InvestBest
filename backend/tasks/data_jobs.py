"""Scheduled data ingestion jobs."""
from backend.tasks.celery_app import app
from datetime import date, timedelta


@app.task
def ingest_daily_prices():
    """Pull latest prices from Polygon and store in DB. Run daily."""
    # TODO: use async DB and Polygon client
    pass


@app.task
def ingest_macro():
    """Pull FRED macro indicators. Run weekly or daily."""
    pass
