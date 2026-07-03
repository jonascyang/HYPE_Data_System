from __future__ import annotations

import datetime as dt
from typing import Any

import httpx


def expiry_to_yyyymmdd(expiry_seconds: int) -> str:
    expiry = dt.datetime.fromtimestamp(expiry_seconds, tz=dt.UTC)
    return expiry.strftime("%Y%m%d")


def ticker_request_payload(expiry_yyyymmdd: str, currency: str = "HYPE") -> dict[str, str]:
    return {
        "currency": currency,
        "instrument_type": "option",
        "expiry_date": expiry_yyyymmdd,
    }


def index_chart_request_payload(
    start_timestamp: int,
    end_timestamp: int,
    *,
    period_seconds: int,
    currency: str = "HYPE",
) -> dict[str, int | str]:
    return {
        "currency": currency,
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "period": period_seconds,
    }


class DeriveClient:
    def __init__(
        self,
        base_url: str = "https://api.lyra.finance",
        currency: str = "HYPE",
        timeout: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.currency = currency
        self.timeout = timeout

    def get_instruments(self) -> dict[str, Any]:
        return self._post(
            "/public/get_instruments",
            {
                "currency": self.currency,
                "expired": False,
                "instrument_type": "option",
            },
        )

    def get_tickers(self, expiry_yyyymmdd: str) -> dict[str, Any]:
        return self._post(
            "/public/get_tickers",
            ticker_request_payload(expiry_yyyymmdd, currency=self.currency),
        )

    def get_index_chart_data(
        self,
        *,
        start_timestamp: int,
        end_timestamp: int,
        period_seconds: int,
    ) -> dict[str, Any]:
        return self._post(
            "/public/get_index_chart_data",
            index_chart_request_payload(
                start_timestamp,
                end_timestamp,
                period_seconds=period_seconds,
                currency=self.currency,
            ),
        )

    def get_trade_history(
        self,
        *,
        currency: str | None = None,
        instrument_type: str = "option",
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
        page: int = 1,
        page_size: int = 1000,
        tx_status: str = "settled",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "currency": currency or self.currency,
            "instrument_type": instrument_type,
            "page": page,
            "page_size": page_size,
            "tx_status": tx_status,
        }
        if from_timestamp is not None:
            payload["from_timestamp"] = from_timestamp
        if to_timestamp is not None:
            payload["to_timestamp"] = to_timestamp
        return self._post("/public/get_trade_history", payload)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise RuntimeError(f"Derive API error on {path}: {data['error']}")
        return data
