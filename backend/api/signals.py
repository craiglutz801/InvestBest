"""REST API for signals: list, filter by strategy/symbol."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models import Signal

router = APIRouter()


class SignalOut(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    signal: str
    confidence: Optional[float] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[SignalOut])
async def list_signals(
    session: AsyncSession = Depends(get_session),
    strategy_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    q = select(Signal).order_by(Signal.id.desc()).limit(limit)
    if strategy_id is not None:
        q = q.where(Signal.strategy_id == strategy_id)
    if symbol is not None:
        q = q.where(Signal.symbol == symbol.upper())
    result = await session.execute(q)
    return list(result.scalars().all())
