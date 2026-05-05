"""Signal generation and portfolio jobs."""
from backend.tasks.celery_app import app


@app.task
def generate_signals():
    """Run all active strategies and persist signals. Run intraday or daily."""
    pass


@app.task
def rebalance_portfolio():
    """Compute target positions and submit orders (paper/live)."""
    pass
