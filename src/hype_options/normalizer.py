from __future__ import annotations

import json
import math
import re
from typing import Any

from hype_options.derive_client import expiry_to_yyyymmdd
from hype_options.models import Instrument, TickerSnapshot


INSTRUMENT_RE = re.compile(
    r"^HYPE-(?P<expiry>\d{8})-(?P<strike>[0-9._]+)-(?P<option_type>[CP])$"
)


def normalize_instruments(payload: dict[str, Any], seen_ms: int) -> list[Instrument]:
    rows: list[Instrument] = []
    for item in payload.get("result", []):
        details = item.get("option_details") or {}
        expiry_seconds = int(details["expiry"])
        raw_json = json.dumps(item, separators=(",", ":"), sort_keys=True)
        rows.append(
            Instrument(
                instrument_name=item["instrument_name"],
                instrument_type=item["instrument_type"],
                base_currency=item["base_currency"],
                quote_currency=item["quote_currency"],
                expiry_ts_ms=expiry_seconds * 1000,
                expiry_yyyymmdd=expiry_to_yyyymmdd(expiry_seconds),
                strike=float(details["strike"]),
                option_type=details["option_type"],
                is_active=bool(item["is_active"]),
                activation_ts_ms=_seconds_to_ms(item.get("scheduled_activation")),
                deactivation_ts_ms=_seconds_to_ms(item.get("scheduled_deactivation")),
                tick_size=_to_float(item.get("tick_size")),
                min_amount=_to_float(item.get("minimum_amount")),
                max_amount=_to_float(item.get("maximum_amount")),
                amount_step=_to_float(item.get("amount_step")),
                maker_fee_rate=_to_float(item.get("maker_fee_rate")),
                taker_fee_rate=_to_float(item.get("taker_fee_rate")),
                base_asset_address=item.get("base_asset_address"),
                base_asset_sub_id=str(item["base_asset_sub_id"])
                if item.get("base_asset_sub_id") is not None
                else None,
                raw_json=raw_json,
                first_seen_ms=seen_ms,
                last_seen_ms=seen_ms,
            )
        )
    return rows


def normalize_tickers(
    payload: dict[str, Any],
    expiry_ts_ms: int,
    expiry_yyyymmdd: str,
    snapshot_ms: int,
    raw_payload_id: str | None,
) -> list[TickerSnapshot]:
    tickers = payload.get("result", {}).get("tickers", {})
    rows: list[TickerSnapshot] = []
    for instrument_name, item in tickers.items():
        match = INSTRUMENT_RE.match(instrument_name)
        if not match:
            continue

        pricing = item.get("option_pricing") or {}
        stats = item.get("stats") or {}
        strike = float(match.group("strike").replace("_", "."))
        option_type = match.group("option_type")

        bid_price = _to_float(item.get("b"))
        ask_price = _to_float(item.get("a"))
        bid_size = _to_float(item.get("B"))
        ask_size = _to_float(item.get("A"))
        mark_price = _to_float(item.get("M"))
        index_price = _to_float(item.get("I"))
        forward_price = _to_float(pricing.get("f"))
        mark_iv = _to_float(pricing.get("i"))
        bid_iv = _to_float(pricing.get("bi"))
        ask_iv = _to_float(pricing.get("ai"))
        delta = _to_float(pricing.get("d"))
        open_interest = _to_float(stats.get("oi"))
        volume = _to_float(stats.get("v"))
        trade_count = _to_int(stats.get("n"))

        mid_price, spread_abs, spread_bps = _spread_fields(bid_price, ask_price)
        surface_quality = classify_surface_quality(
            mark_iv=mark_iv,
            delta=delta,
            bid_price=bid_price,
            ask_price=ask_price,
            open_interest=open_interest,
            volume=volume,
            trade_count=trade_count,
        )
        rows.append(
            TickerSnapshot(
                ts_ms=snapshot_ms,
                source_ts_ms=_to_int(item.get("t")),
                instrument_name=instrument_name,
                expiry_ts_ms=expiry_ts_ms,
                expiry_yyyymmdd=expiry_yyyymmdd,
                strike=strike,
                option_type=option_type,
                index_price=index_price,
                mark_price=mark_price,
                forward_price=forward_price,
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=bid_size,
                ask_size=ask_size,
                mid_price=mid_price,
                spread_abs=spread_abs,
                spread_bps=spread_bps,
                mark_iv=mark_iv,
                bid_iv=bid_iv,
                ask_iv=ask_iv,
                delta=delta,
                gamma=_to_float(pricing.get("g")),
                vega=_to_float(pricing.get("v")),
                theta=_to_float(pricing.get("t")),
                rho=_to_float(pricing.get("rho")),
                rate=_to_float(pricing.get("r")),
                open_interest=open_interest,
                volume=volume,
                trade_count=trade_count,
                high_price=_to_float(stats.get("h")),
                low_price=_to_float(stats.get("l")),
                surface_quality=surface_quality,
                raw_payload_id=raw_payload_id,
            )
        )
    return rows


def classify_surface_quality(
    *,
    mark_iv: float | None,
    delta: float | None,
    bid_price: float | None,
    ask_price: float | None,
    open_interest: float | None,
    volume: float | None,
    trade_count: int | None,
) -> str:
    if mark_iv is None or delta is None:
        return "invalid"
    has_market_signal = any(
        _positive(value)
        for value in (bid_price, ask_price, open_interest, volume, trade_count)
    )
    return "tradable" if has_market_signal else "model"


def _seconds_to_ms(value: Any) -> int | None:
    if value is None:
        return None
    return int(value) * 1000


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive(value: float | int | None) -> bool:
    return value is not None and value > 0


def _spread_fields(
    bid_price: float | None,
    ask_price: float | None,
) -> tuple[float | None, float | None, float | None]:
    if bid_price is None or ask_price is None or bid_price <= 0 or ask_price <= 0:
        return None, None, None
    mid = (bid_price + ask_price) / 2
    spread = ask_price - bid_price
    spread_bps = spread / mid * 10_000 if mid > 0 else None
    return mid, spread, spread_bps
