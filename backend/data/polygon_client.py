"""
Polygon.io client for equity prices. Requires POLYGON_API_KEY.
"""
from datetime import date
from typing import Any
import httpx
from config.settings import get_settings


async def fetch_bars(symbol: str, from_date: date, to_date: date) -> list[dict[str, Any]]:
    """Fetch daily OHLCV bars for symbol. Returns list of dicts."""
    settings = get_settings()
    if not settings.polygon_api_key:
        return []
    url = "https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{from_}/{to}".format(
        symbol=symbol,
        from_=from_date.isoformat(),
        to=to_date.isoformat(),
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params={"apiKey": settings.polygon_api_key}, timeout=30.0)
    if r.status_code != 200:
        return []
    data = r.json()
    results = data.get("results") or []
    return [
        {
            "symbol": symbol,
            "timestamp": f"{x['t']}",
            "open": x["o"],
            "high": x["h"],
            "low": x["l"],
            "close": x["c"],
            "volume": x.get("v", 0),
        }
        for x in results
    ]
