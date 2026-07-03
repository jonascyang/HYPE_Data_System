from __future__ import annotations

import datetime as dt
import time
from typing import Any, Callable, Iterable

from hype_options.derive_client import DeriveClient
from hype_options.instruments import (
    format_option_instrument,
    option_type_name,
    parse_option_instrument_name,
)
from hype_options.portfolio_risk import missing_ticker_requests


TickerMap = dict[str, dict[str, Any]]
ClientFactory = Callable[..., Any]
CurrentTickerMap = Callable[[], TickerMap]


def ticker_map_from_payload(
    payload: dict[str, Any],
    current_ticker_map: CurrentTickerMap,
) -> TickerMap:
    provided = payload.get("tickerByInstrument") or payload.get("ticker_by_instrument")
    if isinstance(provided, dict):
        return provided
    return current_ticker_map()


def complete_ticker_map_for_positions(
    positions: list[dict[str, Any]],
    ticker_map: TickerMap,
    *,
    settings: Any | None = None,
    client_factory: ClientFactory | None = None,
) -> TickerMap:
    requests = missing_ticker_requests(positions, ticker_map)
    if not requests:
        return ticker_map

    completed = dict(ticker_map)
    if settings is None:
        return completed

    factory = client_factory or DeriveClient
    base_url = getattr(settings, "derive_base_url", "https://api.lyra.finance")
    for currency, expiry in sorted(requests):
        try:
            payload = factory(base_url=base_url, currency=currency).get_tickers(expiry)
        except Exception:
            continue
        completed.update(ticker_map_from_ticker_payload(payload, expiry))
    return completed


def ticker_map_from_ticker_payload(payload: dict[str, Any], expiry: str) -> TickerMap:
    raw_tickers = (payload.get("result") or {}).get("tickers") or {}
    ticker_map: TickerMap = {}
    for instrument, item in _ticker_items(raw_tickers):
        if not isinstance(item, dict):
            continue
        ticker = ticker_from_raw_payload(str(instrument), item, expiry)
        if ticker is not None:
            ticker_map[ticker["instrumentName"]] = ticker
    return ticker_map


def ticker_from_raw_payload(
    instrument: str,
    item: dict[str, Any],
    expiry: str,
) -> dict[str, Any] | None:
    parsed = parse_option_instrument_name(instrument)
    if parsed is None:
        return None
    canonical_instrument = parsed.instrument_name
    normalized_expiry = parsed.expiry or str(expiry).replace("-", "")
    pricing = item.get("option_pricing") or {}
    if not isinstance(pricing, dict):
        pricing = {}
    return {
        "instrumentName": canonical_instrument,
        "expiryTsMs": expiry_ms(normalized_expiry),
        "expiry": normalized_expiry,
        "strike": parsed.strike,
        "optionType": parsed.option_type,
        "indexPrice": optional_num(item.get("I")),
        "markPrice": optional_num(item.get("M")),
        "forwardPrice": optional_num(pricing.get("f")),
        "bidPrice": optional_num(item.get("b")),
        "askPrice": optional_num(item.get("a")),
        "markIv": optional_num(pricing.get("i")),
        "delta": optional_num(pricing.get("d")),
        "gamma": optional_num(pricing.get("g")),
        "vega": optional_num(pricing.get("v")),
        "theta": optional_num(pricing.get("t")),
    }


def ticker_map_from_latest_database_snapshot(conn: Any) -> TickerMap:
    row = conn.execute("SELECT max(ts_ms) FROM derive_ticker_snapshots").fetchone()
    if not row or row[0] is None:
        return {}
    rows = conn.execute(
        """
        SELECT
          instrument_name, expiry_ts_ms, expiry_yyyymmdd,
          strike, option_type, index_price, mark_price,
          forward_price, bid_price, ask_price, mark_iv,
          delta, gamma, vega, theta
        FROM derive_ticker_snapshots
        WHERE ts_ms = ?
          AND surface_quality != 'invalid'
        ORDER BY expiry_ts_ms, strike, option_type
        """,
        (row[0],),
    ).fetchall()
    return {_row[0]: serialize_ticker_row(_row) for _row in rows}


def ticker_map_from_realtime_snapshot(snapshot: Any | None) -> TickerMap:
    if snapshot is None:
        return {}
    bootstrap = getattr(snapshot, "bootstrap", None)
    if not isinstance(bootstrap, dict):
        return {}
    by_expiry = bootstrap.get("ivSmileByExpiry") or {}
    if not isinstance(by_expiry, dict):
        return {}

    ticker_map: TickerMap = {}
    for expiry, points in by_expiry.items():
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            strike = point.get("strike")
            if strike is None:
                continue
            for option_type, keys in (
                (
                    "C",
                    {
                        "iv": "callIv",
                        "delta": "callDelta",
                        "gamma": "callGamma",
                        "vega": "callVega",
                        "theta": "callTheta",
                        "premium": "callPremium",
                    },
                ),
                (
                    "P",
                    {
                        "iv": "putIv",
                        "delta": "putDelta",
                        "gamma": "putGamma",
                        "vega": "putVega",
                        "theta": "putTheta",
                        "premium": "putPremium",
                    },
                ),
            ):
                if point.get(keys["iv"]) is None:
                    continue
                instrument = format_option_instrument("HYPE", str(expiry), float(strike), option_type)
                ticker_map[instrument] = {
                    "instrumentName": instrument,
                    "expiry": str(expiry),
                    "strike": float(strike),
                    "optionType": option_type,
                    "markIv": point.get(keys["iv"]),
                    "markPrice": point.get(keys["premium"]),
                    "delta": point.get(keys["delta"]),
                    "gamma": point.get(keys["gamma"]),
                    "vega": point.get(keys["vega"]),
                    "theta": point.get(keys["theta"]),
                }
    return ticker_map


def serialize_ticker_row(row: Any) -> dict[str, Any]:
    (
        instrument_name,
        expiry_ts_ms,
        expiry,
        strike,
        option_type,
        index_price,
        mark_price,
        forward_price,
        bid_price,
        ask_price,
        mark_iv,
        delta,
        gamma,
        vega,
        theta,
    ) = row
    return {
        "instrumentName": instrument_name,
        "expiryTsMs": expiry_ts_ms,
        "expiry": expiry,
        "strike": optional_num(strike),
        "optionType": option_type,
        "indexPrice": optional_num(index_price),
        "markPrice": optional_num(mark_price),
        "forwardPrice": optional_num(forward_price),
        "bidPrice": optional_num(bid_price),
        "askPrice": optional_num(ask_price),
        "markIv": optional_num(mark_iv),
        "delta": optional_num(delta),
        "gamma": optional_num(gamma),
        "vega": optional_num(vega),
        "theta": optional_num(theta),
    }


def option_choices(ticker_map: TickerMap, *, now_ms: int | None = None) -> list[dict[str, Any]]:
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    return sorted(
        (option_choice(item) for item in ticker_map.values() if is_unexpired_ticker(item, now_ms)),
        key=lambda item: (
            str(item.get("expiry") or ""),
            float(item.get("strike") or 0),
            str(item.get("optionType") or ""),
        ),
    )


def option_choice(ticker: dict[str, Any]) -> dict[str, Any]:
    option_type = option_type_name(ticker.get("optionType") or ticker.get("option_type"))
    return {
        "instrumentName": ticker.get("instrumentName") or ticker.get("instrument_name"),
        "expiry": ticker.get("expiry") or ticker.get("expiry_yyyymmdd"),
        "strike": ticker.get("strike"),
        "optionType": option_type,
        "markPrice": ticker.get("markPrice") if "markPrice" in ticker else ticker.get("mark_price"),
        "bidPrice": ticker.get("bidPrice") if "bidPrice" in ticker else ticker.get("bid_price"),
        "askPrice": ticker.get("askPrice") if "askPrice" in ticker else ticker.get("ask_price"),
        "spotPrice": ticker.get("indexPrice") if "indexPrice" in ticker else ticker.get("index_price"),
    }


def is_unexpired_ticker(ticker: dict[str, Any], now_ms: int) -> bool:
    expiry_timestamp_ms = safe_num(ticker.get("expiryTsMs") if "expiryTsMs" in ticker else ticker.get("expiry_ts_ms"))
    if expiry_timestamp_ms is not None:
        return expiry_timestamp_ms > now_ms
    expiry = str(ticker.get("expiry") or ticker.get("expiry_yyyymmdd") or "")
    if len(expiry) == 8 and expiry.isdigit():
        today = time.strftime("%Y%m%d", time.gmtime(now_ms / 1000))
        return expiry >= today
    return True


def expiry_ms(expiry: str) -> int | None:
    try:
        value = dt.datetime.strptime(str(expiry).replace("-", ""), "%Y%m%d").replace(tzinfo=dt.UTC)
    except ValueError:
        return None
    return int(value.timestamp() * 1000)


def optional_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def safe_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ticker_items(raw_tickers: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(raw_tickers, dict):
        return raw_tickers.items()
    if isinstance(raw_tickers, list):
        items: list[tuple[str, Any]] = []
        for item in raw_tickers:
            if not isinstance(item, dict):
                continue
            instrument = item.get("instrument_name") or item.get("instrumentName")
            if instrument:
                items.append((str(instrument), item))
        return items
    return ()
