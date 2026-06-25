from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    turso_database_url: str
    turso_auth_token: str
    derive_base_url: str = "https://api.lyra.finance"
    derive_currency: str = "HYPE"
    derive_collection_interval_seconds: int = 300
    raw_payload_retention_days: int = 3
    ticker_retention_days: int = 7
    gex_by_strike_retention_days: int = 7
    collection_run_retention_days: int = 90

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            turso_database_url=_required_env("TURSO_DATABASE_URL"),
            turso_auth_token=_required_env("TURSO_AUTH_TOKEN"),
            derive_base_url=os.getenv("DERIVE_BASE_URL", "https://api.lyra.finance"),
            derive_currency=os.getenv("DERIVE_CURRENCY", "HYPE"),
            derive_collection_interval_seconds=int(
                os.getenv("DERIVE_COLLECTION_INTERVAL_SECONDS", "300")
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
