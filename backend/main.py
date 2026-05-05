"""
InvestBest — FastAPI application entry point.
Serves API + dashboard on localhost.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.api import dashboard, notifications, strategies, signals, system
from backend.db import init_db
from config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB connection pool. Shutdown: cleanup."""
    await init_db()
    yield
    # Teardown if needed
    pass


app = FastAPI(
    title="InvestBest",
    description="AI-powered quantitative research and trading platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static assets and templates for dashboard
frontend_root = Path(__file__).resolve().parent.parent / "frontend"
if frontend_root.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_root / "static")), name="static")
    templates = Jinja2Templates(directory=str(frontend_root / "templates"))
    app.state.templates = templates
else:
    templates = None
    app.state.templates = None

# API routers
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(system.router, prefix="/api/system", tags=["system"])


@app.get("/")
async def root():
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/health")
async def health():
    """Health check for monitoring."""
    settings = get_settings()
    return {
        "status": "ok",
        "polygon_configured": settings.is_configured_polygon,
        "alpaca_configured": settings.is_configured_alpaca,
        "fred_configured": settings.is_configured_fred,
    }
