from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_auth_token: str
    order_flow_database_url: str
    order_flow_database_auth_token: str
    derive_base_url: str = "https://api.lyra.finance"
    derive_app_base_url: str = "https://app.derive.xyz"
    derive_currency: str = "HYPE"
    derive_collection_interval_seconds: int = 300
    derive_instrument_refresh_seconds: int = 600
    options_realtime_refresh_seconds: int = 15
    options_history_write_seconds: int = 300
    options_history_lookback_days: int = 365
    raw_payload_retention_days: int = 3
    ticker_retention_days: int = 7
    gex_by_strike_retention_days: int = 7
    collection_run_retention_days: int = 90

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = _database_url_from_env()
        database_auth_token = _database_auth_token_from_env()
        return cls(
            database_url=database_url,
            database_auth_token=database_auth_token,
            order_flow_database_url=_order_flow_database_url_from_env(database_url),
            order_flow_database_auth_token=_order_flow_database_auth_token_from_env(
                database_auth_token
            ),
            derive_base_url=os.getenv("DERIVE_BASE_URL", "https://api.lyra.finance"),
            derive_app_base_url=os.getenv("DERIVE_APP_BASE_URL", "https://app.derive.xyz"),
            derive_currency=os.getenv("DERIVE_CURRENCY", "HYPE"),
            derive_collection_interval_seconds=int(
                os.getenv("DERIVE_COLLECTION_INTERVAL_SECONDS", "300")
            ),
            derive_instrument_refresh_seconds=int(
                os.getenv("DERIVE_INSTRUMENT_REFRESH_SECONDS", "600")
            ),
            options_realtime_refresh_seconds=int(
                os.getenv("OPTIONS_REALTIME_REFRESH_SECONDS", "15")
            ),
            options_history_write_seconds=int(
                os.getenv("OPTIONS_HISTORY_WRITE_SECONDS", "300")
            ),
            options_history_lookback_days=int(
                os.getenv("OPTIONS_HISTORY_LOOKBACK_DAYS", "365")
            ),
            raw_payload_retention_days=int(os.getenv("RAW_PAYLOAD_RETENTION_DAYS", "3")),
            ticker_retention_days=int(os.getenv("TICKER_RETENTION_DAYS", "7")),
            gex_by_strike_retention_days=int(os.getenv("GEX_BY_STRIKE_RETENTION_DAYS", "7")),
            collection_run_retention_days=int(os.getenv("COLLECTION_RUN_RETENTION_DAYS", "90")),
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _database_url_from_env() -> str:
    value = os.getenv("DATABASE_URL") or os.getenv("TURSO_DATABASE_URL")
    if not value:
        raise RuntimeError("Missing required environment variable: DATABASE_URL")
    return value


def _database_auth_token_from_env() -> str:
    return os.getenv("DATABASE_AUTH_TOKEN") or os.getenv("TURSO_AUTH_TOKEN", "")


def _order_flow_database_url_from_env(default_database_url: str) -> str:
    return os.getenv("ORDER_FLOW_DATABASE_URL") or default_database_url


def _order_flow_database_auth_token_from_env(default_database_auth_token: str) -> str:
    if os.getenv("ORDER_FLOW_DATABASE_URL"):
        return os.getenv("ORDER_FLOW_DATABASE_AUTH_TOKEN", "")
    return os.getenv("ORDER_FLOW_DATABASE_AUTH_TOKEN") or default_database_auth_token
