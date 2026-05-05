"""Dashboard pages: main view, strategy designer, signals, notifications, system status."""
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _templates(request: Request):
    t = getattr(request.app.state, "templates", None)
    if t is None:
        raise ValueError("Templates not mounted. Ensure frontend/templates exists.")
    return t


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main dashboard: portfolio, PnL, active strategies, risk."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "InvestBest — Dashboard"},
    )


@router.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Strategy explorer and designer."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "strategies.html",
        {"request": request, "title": "InvestBest — Strategies"},
    )


@router.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Live signals from strategies."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "signals.html",
        {"request": request, "title": "InvestBest — Signals"},
    )


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """Notification history and settings."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "notifications.html",
        {"request": request, "title": "InvestBest — Notifications"},
    )


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    """System status, data health, services checklist."""
    templates = _templates(request)
    return templates.TemplateResponse(
        "system.html",
        {"request": request, "title": "InvestBest — System"},
    )
