from typing import Optional
from sqlalchemy import String, Text, Float, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from backend.db.base import Base, TimestampMixin


class StrategyStatus(str, enum.Enum):
    draft = "draft"
    backtesting = "backtesting"
    active = "active"
    paused = "paused"
    retired = "retired"


class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # e.g. strategies.momentum
    status: Mapped[str] = mapped_column(String(32), default=StrategyStatus.draft.value)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON params

    results = relationship("StrategyResult", back_populates="strategy", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="strategy", cascade="all, delete-orphan")


class StrategyResult(Base, TimestampMixin):
    __tablename__ = "strategy_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    sharpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    backtest_start: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    backtest_end: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    strategy = relationship("Strategy", back_populates="results")
