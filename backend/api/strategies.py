"""REST API for strategies: list, create, update, run backtest."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models import Strategy, StrategyResult
from backend.services.backtest import BacktestService

router = APIRouter()


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    module_path: Optional[str] = None
    config_json: Optional[str] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    config_json: Optional[str] = None


class StrategyOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    module_path: Optional[str] = None
    status: str
    config_json: Optional[str] = None

    class Config:
        from_attributes = True


class StrategyResultOut(BaseModel):
    id: int
    strategy_id: int
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    annual_return: Optional[float] = None
    backtest_start: Optional[str] = None
    backtest_end: Optional[str] = None

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    strategy_id: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("", response_model=list[StrategyOut])
async def list_strategies(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Strategy).order_by(Strategy.id))
    return list(result.scalars().all())


@router.post("", response_model=StrategyOut)
async def create_strategy(body: StrategyCreate, session: AsyncSession = Depends(get_session)):
    s = Strategy(
        name=body.name,
        description=body.description,
        module_path=body.module_path,
        config_json=body.config_json,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@router.get("/{strategy_id}", response_model=StrategyOut)
async def get_strategy(strategy_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Strategy not found")
    return s


@router.patch("/{strategy_id}", response_model=StrategyOut)
async def update_strategy(
    strategy_id: int, body: StrategyUpdate, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Strategy not found")
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.status is not None:
        s.status = body.status
    if body.config_json is not None:
        s.config_json = body.config_json
    await session.commit()
    await session.refresh(s)
    return s


@router.get("/{strategy_id}/results", response_model=list[StrategyResultOut])
async def list_strategy_results(strategy_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(StrategyResult).where(StrategyResult.strategy_id == strategy_id).order_by(StrategyResult.id.desc())
    )
    return list(result.scalars().all())


@router.post("/backtest")
async def run_backtest(body: BacktestRequest, session: AsyncSession = Depends(get_session)):
    """Run backtest for a strategy; returns metrics and optionally stores StrategyResult."""
    result = await session.execute(select(Strategy).where(Strategy.id == body.strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    service = BacktestService(session)
    metrics = await service.run(strategy, body.start_date, body.end_date)
    return {"strategy_id": body.strategy_id, "metrics": metrics}
