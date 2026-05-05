"""System status, health, and services checklist."""
from fastapi import APIRouter
from config.settings import get_settings

router = APIRouter()


@router.get("/status")
async def system_status():
    """Aggregated status for dashboard."""
    s = get_settings()
    return {
        "data": {
            "polygon": "configured" if s.is_configured_polygon else "missing",
            "alpaca": "configured" if s.is_configured_alpaca else "missing",
            "fred": "configured" if s.is_configured_fred else "missing",
            "openai": "configured" if s.openai_api_key else "missing",
        },
        "redis": s.redis_url.startswith("redis"),
    }


@router.get("/services-checklist")
async def services_checklist():
    """Return the same structure as SERVICES_CHECKLIST for the UI."""
    s = get_settings()
    return {
        "data_providers": [
            {"name": "Polygon", "configured": bool(s.polygon_api_key)},
            {"name": "Alpha Vantage", "configured": bool(s.alpha_vantage_api_key)},
            {"name": "FRED", "configured": bool(s.fred_api_key)},
        ],
        "broker": [
            {"name": "Alpaca", "configured": s.is_configured_alpaca},
        ],
        "ai": [
            {"name": "OpenAI", "configured": bool(s.openai_api_key)},
        ],
        "notifications": [
            {"name": "SMTP", "configured": bool(s.smtp_host and s.smtp_user)},
            {"name": "Slack", "configured": bool(s.slack_webhook_url)},
            {"name": "Telegram", "configured": bool(s.telegram_bot_token and s.telegram_chat_id)},
        ],
    }
