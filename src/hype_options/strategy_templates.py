from __future__ import annotations

from typing import Any

from hype_options.instruments import (
    format_option_instrument,
    format_strike,
    normalize_expiry,
    option_type_code,
    parse_option_instrument_name,
)


SUPPORTED_STRATEGIES = (
    "long_call",
    "long_put",
    "vertical_call_spread",
    "vertical_put_spread",
    "straddle",
    "strangle",
    "risk_reversal",
    "butterfly",
    "iron_condor",
    "calendar_spread",
    "custom",
)
GREEK_FIELDS = ("delta", "gamma", "vega", "theta")


def generate_strategy_legs(
    strategy: str,
    *,
    expiry: str,
    strikes: list[float],
    quantity: float = 1.0,
    side: str = "buy",
    custom_legs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    strategy = _normalize_strategy(strategy)
    side = _normalize_side(side)
    quantity = _positive_float(quantity, "quantity")
    expiry = _normalize_expiry(expiry)
    sorted_strikes = sorted(_positive_float(strike, "strike") for strike in strikes)

    if strategy == "custom":
        return [_normalize_leg(leg, expiry=expiry, quantity=quantity) for leg in (custom_legs or [])]
    if strategy == "calendar_spread":
        if custom_legs is None:
            raise ValueError("Calendar spread requires custom legs with individual expiries")
        return [_normalize_leg(leg, expiry=expiry, quantity=quantity) for leg in custom_legs]
    if strategy == "long_call":
        strike = _require_strikes(sorted_strikes, 1)[0]
        return [_leg(expiry, strike, "C", side, quantity)]
    if strategy == "long_put":
        strike = _require_strikes(sorted_strikes, 1)[0]
        return [_leg(expiry, strike, "P", side, quantity)]
    if strategy == "vertical_call_spread":
        low, high = _require_strikes(sorted_strikes, 2)
        return [
            _leg(expiry, low, "C", side, quantity),
            _leg(expiry, high, "C", _opposite_side(side), quantity),
        ]
    if strategy == "vertical_put_spread":
        low, high = _require_strikes(sorted_strikes, 2)
        return [
            _leg(expiry, high, "P", side, quantity),
            _leg(expiry, low, "P", _opposite_side(side), quantity),
        ]
    if strategy == "straddle":
        strike = _require_strikes(sorted_strikes, 1)[0]
        return [
            _leg(expiry, strike, "C", side, quantity),
            _leg(expiry, strike, "P", side, quantity),
        ]
    if strategy == "strangle":
        low, high = _require_strikes(sorted_strikes, 2)
        return [
            _leg(expiry, low, "P", side, quantity),
            _leg(expiry, high, "C", side, quantity),
        ]
    if strategy == "risk_reversal":
        low, high = _require_strikes(sorted_strikes, 2)
        return [
            _leg(expiry, low, "P", _opposite_side(side), quantity),
            _leg(expiry, high, "C", side, quantity),
        ]
    if strategy == "butterfly":
        low, mid, high = _require_strikes(sorted_strikes, 3)
        return [
            _leg(expiry, low, "C", side, quantity),
            _leg(expiry, mid, "C", _opposite_side(side), quantity * 2),
            _leg(expiry, high, "C", side, quantity),
        ]
    if strategy == "iron_condor":
        low_put, high_put, low_call, high_call = _require_strikes(sorted_strikes, 4)
        return [
            _leg(expiry, low_put, "P", _opposite_side(side), quantity),
            _leg(expiry, high_put, "P", side, quantity),
            _leg(expiry, low_call, "C", side, quantity),
            _leg(expiry, high_call, "C", _opposite_side(side), quantity),
        ]
    raise ValueError(f"Unsupported strategy: {strategy}")


def simulate_strategy(
    legs: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    totals = {"premium": 0.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    for raw_leg in legs:
        leg = _normalize_leg(raw_leg)
        instrument = leg["instrumentName"]
        ticker = ticker_by_instrument.get(instrument)
        if ticker is None:
            raise ValueError(f"Missing ticker for instrument: {instrument}")
        signed_quantity = leg["quantity"] if leg["side"] == "buy" else -leg["quantity"]
        mark_price = _float(ticker.get("markPrice") or ticker.get("mark_price")) or 0.0
        premium = mark_price * -signed_quantity
        row = {
            **leg,
            "signedQuantity": signed_quantity,
            "markPrice": mark_price,
            "premium": _round(premium),
        }
        totals["premium"] += premium
        for field in GREEK_FIELDS:
            unit_value = _float(ticker.get(field)) or 0.0
            value = unit_value * signed_quantity
            row[field] = _round(value)
            totals[field] += value
        rows.append(row)
    return {
        "legs": rows,
        "totals": {field: _round(value) for field, value in totals.items()},
    }


def _normalize_strategy(strategy: str) -> str:
    strategy = str(strategy).lower()
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unsupported strategy: {strategy}")
    return strategy


def _leg(expiry: str, strike: float, option_type: str, side: str, quantity: float) -> dict[str, Any]:
    strike = float(strike)
    option_type = option_type.upper()
    return {
        "instrumentName": _instrument_name(expiry, strike, option_type),
        "expiry": expiry,
        "strike": strike,
        "optionType": option_type,
        "side": side,
        "quantity": float(quantity),
    }


def _normalize_leg(
    raw_leg: dict[str, Any],
    *,
    expiry: str | None = None,
    quantity: float | None = None,
) -> dict[str, Any]:
    side = _normalize_side(raw_leg.get("side", "buy"))
    leg_quantity = _positive_float(raw_leg.get("quantity", quantity or 1.0), "quantity")
    raw_instrument = raw_leg.get("instrumentName") or raw_leg.get("instrument_name")
    parsed = _parse_instrument(str(raw_instrument)) if raw_instrument is not None else {}
    leg_expiry = _normalize_expiry(str(raw_leg.get("expiry") or expiry or parsed.get("expiry") or ""))
    option_type = option_type_code(raw_leg.get("optionType") or raw_leg.get("option_type") or parsed.get("optionType") or "C")
    if option_type is None:
        raise ValueError(f"Unsupported option type: {raw_leg.get('optionType') or raw_leg.get('option_type')}")
    strike = _positive_float(raw_leg.get("strike"), "strike") if raw_leg.get("strike") is not None else parsed.get("strike")
    if strike is None:
        if raw_instrument is None:
            raise ValueError("Custom leg requires instrumentName or strike")
        strike = _strike_from_instrument(str(raw_instrument))
    currency = str(parsed.get("currency") or "HYPE")
    instrument = _instrument_name(leg_expiry, strike, option_type, currency=currency)
    return {
        "instrumentName": instrument,
        "expiry": leg_expiry,
        "strike": strike,
        "optionType": option_type,
        "side": side,
        "quantity": leg_quantity,
    }


def _instrument_name(expiry: str, strike: float, option_type: str, *, currency: str = "HYPE") -> str:
    return format_option_instrument(currency, expiry, strike, option_type)


def _format_strike(strike: float) -> str:
    return format_strike(strike)


def _strike_from_instrument(instrument: str) -> float:
    parsed = _parse_instrument(instrument)
    if parsed.get("strike") is not None:
        return parsed["strike"]
    raise ValueError(f"Cannot parse strike from instrument: {instrument}")


def _parse_instrument(instrument: str) -> dict[str, Any]:
    parsed = parse_option_instrument_name(instrument)
    if parsed is None:
        return {}
    return {
        "currency": parsed.currency,
        "expiry": parsed.expiry,
        "strike": parsed.strike,
        "optionType": parsed.option_type,
    }


def _normalize_expiry(expiry: str) -> str:
    return normalize_expiry(expiry)


def _normalize_side(side: Any) -> str:
    side = str(side).lower()
    if side not in {"buy", "sell"}:
        raise ValueError(f"Unsupported side: {side}")
    return side


def _opposite_side(side: str) -> str:
    return "sell" if side == "buy" else "buy"


def _require_strikes(strikes: list[float], count: int) -> list[float]:
    if len(strikes) < count:
        raise ValueError(f"Strategy requires at least {count} strike(s)")
    return strikes[:count]


def _positive_float(value: Any, name: str) -> float:
    result = _float(value)
    if result is None or result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    return round(float(value), 12)
