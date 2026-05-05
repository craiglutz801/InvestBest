"""Async SQLAlchemy engine and session. Falls back to in-memory SQLite if no DATABASE_URL."""
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config.settings import get_settings

_database_url = get_settings().database_url
if _database_url.startswith("postgresql+asyncpg"):
    _engine = create_async_engine(
        _database_url,
        echo=get_settings().debug,
        pool_pre_ping=True,
    )
else:
    # SQLite (default or explicit sqlite+aiosqlite:///...)
    if _database_url.startswith("sqlite"):
        # Extract path from URL if present, else default
        _db_path = _database_url.replace("sqlite+aiosqlite:///", "").strip() or "investbest.db"
    else:
        _db_path = os.environ.get("INVESTBEST_DB_PATH", "investbest.db")
    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{_db_path}",
        echo=get_settings().debug,
        connect_args={"check_same_thread": False},
    )

async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async_engine = _engine


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def init_db():
    """Create tables if they don't exist. Call on startup."""
    from backend.db import base
    import backend.models  # noqa: F401 — register models with Base.metadata
    async with _engine.begin() as conn:
        await conn.run_sync(base.Base.metadata.create_all)
