"""Application settings loaded from environment."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"

    # Database (default SQLite for local; set DATABASE_URL for PostgreSQL)
    database_url: str = "sqlite+aiosqlite:///investbest.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Data providers
    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""

    # Broker
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # AI
    openai_api_key: str = ""

    # Notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def is_configured_polygon(self) -> bool:
        return bool(self.polygon_api_key)

    @property
    def is_configured_alpaca(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)

    @property
    def is_configured_fred(self) -> bool:
        return bool(self.fred_api_key)


def get_settings() -> Settings:
    return Settings()
