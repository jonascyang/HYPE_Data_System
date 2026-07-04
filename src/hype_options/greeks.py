from __future__ import annotations

import math
import time
from typing import Any

from hype_options.instruments import (
    extract_instrument_name,
    instrument_underlying,
    is_option_instrument,
    is_perp_instrument,
    option_type_code,
    parse_option_instrument_name,
)


GREEK_FIELDS = ("delta", "gamma", "vega", "theta")
MS_PER_YEAR = 365 * 24 * 60 * 60 * 1000
NEAR_ZERO = 1e-12


def sum_position_greeks(positions: list[dict[str, Any]]) -> dict[str, float]:
    totals = {field: 0.0 for field in GREEK_FIELDS}
    for position in positions:
        for field in GREEK_FIELDS:
            value = _to_float(position.get(field))
            if value is not None:
                totals[field] += value
    return {field: _round(value) for field, value in totals.items()}


def normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def black_d1(forward: float, strike: float, volatility: float, years_to_expiry: float) -> float:
    return (
        math.log(forward / strike) + 0.5 * volatility * volatility * years_to_expiry
    ) / (volatility * math.sqrt(years_to_expiry))


def black_d2(forward: float, strike: float, volatility: float, years_to_expiry: float) -> float:
    return black_d1(forward, strike, volatility, years_to_expiry) - volatility * math.sqrt(years_to_expiry)


def black_forward_greeks(
    *,
    forward: float,
    strike: float,
    volatility: float,
    years_to_expiry: float,
    option_type: str,
) -> dict[str, float] | None:
    if forward <= 0 or strike <= 0 or volatility <= 0 or years_to_expiry <= 0:
        return None
    d1 = black_d1(forward, strike, volatility, years_to_expiry)
    pdf = normal_pdf(d1)
    option = option_type.upper()
    if option == "C":
        delta = normal_cdf(d1)
    elif option == "P":
        delta = normal_cdf(d1) - 1
    else:
        return None
    sqrt_t = math.sqrt(years_to_expiry)
    return {
        "delta": delta,
        "gamma": pdf / (forward * volatility * sqrt_t),
        "vega": forward * pdf * sqrt_t,
        "theta": -(forward * pdf * volatility) / (2 * sqrt_t),
    }


def build_portfolio_curve(
    selected_positions: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
    metric: str,
    shock_min: float = -0.50,
    shock_max: float = 0.50,
    step: float = 0.01,
) -> dict[str, Any]:
    metric = _normalize_metric(metric)
    selected_positions = portfolio_positions(selected_positions)
    totals = sum_position_greeks(selected_positions)
    contributions: list[dict[str, Any]] = []
    flat_greek_contributions: list[float] = []
    payoff_contributions: list[dict[str, Any]] = []
    perp_payoff_contributions: list[dict[str, Any]] = []
    unavailable: list[str] = []
    payoff_unavailable: list[str] = []
    ticker_by_underlying = _ticker_by_underlying(ticker_by_instrument)

    for position in selected_positions:
        instrument = _instrument_name(position)
        if not instrument:
            continue
        if is_perp_position(position):
            perp_delta = _perp_delta(position)
            if metric == "delta":
                if perp_delta is None:
                    unavailable.append(instrument)
                else:
                    flat_greek_contributions.append(perp_delta)
            base_spot = _perp_base_spot(position, ticker_by_underlying)
            if perp_delta is None or base_spot is None:
                payoff_unavailable.append(instrument)
            else:
                perp_payoff_contributions.append(
                    {
                        "instrument": instrument,
                        "delta": perp_delta,
                        "baseSpot": base_spot,
                    }
                )
            continue
        wallet_greek = _to_float(position.get(metric))
        ticker = ticker_by_instrument.get(instrument or "")
        if wallet_greek is None or ticker is None:
            unavailable.append(instrument)
        else:
            current_model_greek = _model_greek_for_ticker(ticker, metric, 0.0)
            if current_model_greek is None or abs(current_model_greek) <= NEAR_ZERO:
                unavailable.append(instrument)
            else:
                contributions.append(
                    {
                        "instrument": instrument,
                        "ticker": ticker,
                        "walletGreek": wallet_greek,
                        "currentModelGreek": current_model_greek,
                    }
                )
        signed_quantity = _signed_quantity(position)
        premium_cashflow = _premium_cashflow(position, ticker, signed_quantity) if ticker is not None and signed_quantity is not None else None
        if not instrument or signed_quantity is None or ticker is None or premium_cashflow is None or _payoff_inputs(ticker) is None:
            if instrument:
                payoff_unavailable.append(instrument)
            continue
        payoff_contributions.append(
            {
                "instrument": instrument,
                "ticker": ticker,
                "signedQuantity": signed_quantity,
                "premiumCashflow": premium_cashflow,
            }
        )

    point_count = int(round((shock_max - shock_min) / step)) + 1
    shock_values = [round(shock_min + index * step, 10) for index in range(point_count)]
    display_base_price = _display_base_price(contributions, payoff_contributions, perp_payoff_contributions)
    points = []
    payoff_points = []
    if contributions or flat_greek_contributions:
        for shock in shock_values:
            value = sum(flat_greek_contributions)
            for contribution in contributions:
                scenario_greek = _model_greek_for_ticker(contribution["ticker"], metric, shock)
                if scenario_greek is None:
                    continue
                value += (
                    contribution["walletGreek"]
                    * scenario_greek
                    / contribution["currentModelGreek"]
                )
            points.append(
                {
                    "shock": round(shock, 2),
                    "shockPct": _round(shock * 100),
                    "spotPrice": _shock_price(display_base_price, shock),
                    "value": _round(value),
                }
            )
    if payoff_contributions or perp_payoff_contributions:
        for shock in shock_values:
            value = 0.0
            scenario_spot = _shock_price(display_base_price, shock)
            for contribution in payoff_contributions:
                payoff_inputs = _payoff_inputs(contribution["ticker"])
                if payoff_inputs is None:
                    continue
                base_forward, strike, option_type = payoff_inputs
                payoff_spot = base_forward * (1 + shock)
                value += (
                    _intrinsic_value(payoff_spot, strike, option_type)
                    * contribution["signedQuantity"]
                    + contribution["premiumCashflow"]
                )
            for contribution in perp_payoff_contributions:
                perp_spot = contribution["baseSpot"] * (1 + shock)
                value += contribution["delta"] * (perp_spot - contribution["baseSpot"])
            payoff_points.append(
                {
                    "shock": round(shock, 2),
                    "shockPct": _round(shock * 100),
                    "spotPrice": scenario_spot,
                    "value": _round(0.0 if abs(value) < 1e-8 else value),
                }
            )
    point_by_shock = {point["shock"]: point for point in points}
    payoff_point_by_shock = {point["shock"]: point for point in payoff_points}
    scenario_table = [
        {
            "shock": shock,
            "shockPct": _round(shock * 100),
            "spotPrice": point_by_shock.get(shock, {"spotPrice": None})["spotPrice"],
            "value": point_by_shock.get(shock, {"value": None})["value"],
        }
        for shock in (-0.2, -0.1, 0.0, 0.1, 0.2)
    ] if points else []
    payoff_scenario_table = [
        {
            "shock": shock,
            "shockPct": _round(shock * 100),
            "spotPrice": payoff_point_by_shock.get(shock, {"spotPrice": None})["spotPrice"],
            "value": payoff_point_by_shock.get(shock, {"value": None})["value"],
        }
        for shock in (-0.2, -0.1, 0.0, 0.1, 0.2)
    ] if payoff_points else []
    return {
        "metric": metric,
        "totals": totals,
        "current": totals[metric],
        "points": points,
        "scenarioTable": scenario_table,
        "unavailableInstruments": sorted(set(unavailable)),
        "payoffPoints": payoff_points,
        "payoffScenarioTable": payoff_scenario_table,
        "payoffUnavailableInstruments": sorted(set(payoff_unavailable)),
    }


def build_portfolio_curve_bundle(
    selected_positions: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
    metric: str,
) -> dict[str, Any]:
    selected_metric = _normalize_metric(metric)
    curves = {
        greek_metric: build_portfolio_curve(selected_positions, ticker_by_instrument, greek_metric)
        for greek_metric in GREEK_FIELDS
    }
    return {
        "metric": selected_metric,
        "curve": curves[selected_metric],
        "curves": curves,
    }


def option_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [position for position in positions if is_option_position(position)]


def portfolio_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [position for position in positions if is_option_position(position) or is_perp_position(position)]


def position_underlyings(positions: list[dict[str, Any]]) -> list[str]:
    return sorted({underlying for position in positions if (underlying := _position_underlying(position))})


def is_option_position(position: dict[str, Any]) -> bool:
    return is_option_instrument(
        _instrument_name(position),
        position.get("instrumentType") or position.get("instrument_type"),
    )


def is_perp_position(position: dict[str, Any]) -> bool:
    return is_perp_instrument(
        _instrument_name(position),
        position.get("instrumentType") or position.get("instrument_type"),
    )


def _model_greek_for_ticker(ticker: dict[str, Any], metric: str, shock: float) -> float | None:
    base_forward = _first_float(ticker, "forwardPrice", "forward_price", "indexPrice", "index_price")
    strike = _first_float(ticker, "strike")
    volatility = _first_float(ticker, "markIv", "mark_iv")
    option_type = _option_type(ticker)
    years_to_expiry = _years_to_expiry(ticker)
    if base_forward is None or strike is None or volatility is None or option_type is None or years_to_expiry is None:
        return None
    greeks = black_forward_greeks(
        forward=base_forward * (1 + shock),
        strike=strike,
        volatility=volatility,
        years_to_expiry=years_to_expiry,
        option_type=option_type,
    )
    return greeks.get(metric) if greeks is not None else None


def _payoff_inputs(ticker: dict[str, Any]) -> tuple[float, float, str] | None:
    base_forward = _ticker_base_spot(ticker)
    strike = _first_float(ticker, "strike")
    option_type = _option_type(ticker)
    if base_forward is None or strike is None or option_type is None:
        return None
    return base_forward, strike, option_type


def _display_base_price(
    contributions: list[dict[str, Any]],
    payoff_contributions: list[dict[str, Any]],
    perp_payoff_contributions: list[dict[str, Any]],
) -> float | None:
    for contribution in contributions:
        base_price = _ticker_base_spot(contribution["ticker"])
        if base_price is not None:
            return base_price
    for contribution in payoff_contributions:
        base_price = _ticker_base_spot(contribution["ticker"])
        if base_price is not None:
            return base_price
    for contribution in perp_payoff_contributions:
        base_price = _to_float(contribution.get("baseSpot"))
        if base_price is not None:
            return base_price
    return None


def _shock_price(base_price: float | None, shock: float) -> float | None:
    if base_price is None:
        return None
    return _round(base_price * (1 + shock))


def _ticker_base_spot(ticker: dict[str, Any]) -> float | None:
    return _first_float(ticker, "forwardPrice", "forward_price", "indexPrice", "index_price", "markPrice", "mark_price")


def _ticker_by_underlying(ticker_by_instrument: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_underlying: dict[str, dict[str, Any]] = {}
    for instrument, ticker in ticker_by_instrument.items():
        underlying = _position_underlying({"instrumentName": instrument, **ticker})
        if underlying and underlying not in by_underlying and _ticker_base_spot(ticker) is not None:
            by_underlying[underlying] = ticker
    return by_underlying


def _intrinsic_value(spot: float, strike: float, option_type: str) -> float:
    if option_type.upper() == "C":
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def _premium_cashflow(
    position: dict[str, Any],
    ticker: dict[str, Any],
    signed_quantity: float,
) -> float | None:
    premium = _first_float(position, "premium")
    if premium is not None:
        return premium
    abs_quantity = abs(signed_quantity)
    if abs_quantity <= NEAR_ZERO:
        return None
    total_premium = _first_float(position, "premiumUsd", "premium_usd")
    if total_premium is not None:
        return -abs(total_premium) if signed_quantity > 0 else abs(total_premium)
    unit_premium = _first_float(position, "entryPrice", "entry_price", "markPrice", "mark_price")
    if unit_premium is None:
        unit_premium = _first_float(ticker, "markPrice", "mark_price")
    if unit_premium is None:
        return None
    return -abs(unit_premium) * signed_quantity


def _signed_quantity(position: dict[str, Any]) -> float | None:
    signed = _first_float(position, "signedQuantity", "signed_quantity")
    if signed is not None:
        return signed
    amount = _first_float(position, "amount")
    quantity = _first_float(position, "quantity")
    raw_size = quantity if quantity is not None else amount
    if raw_size is None:
        return None
    side = str(position.get("side") or "").lower()
    if side in {"sell", "short", "s"}:
        return -abs(raw_size)
    if side in {"buy", "long", "b"}:
        return abs(raw_size)
    return raw_size


def _perp_delta(position: dict[str, Any]) -> float | None:
    delta = _to_float(position.get("delta"))
    if delta is not None:
        return delta
    return _signed_quantity(position)


def _perp_base_spot(position: dict[str, Any], ticker_by_underlying: dict[str, dict[str, Any]]) -> float | None:
    base_spot = _first_float(position, "markPrice", "mark_price", "indexPrice", "index_price", "spotPrice", "spot_price", "entryPrice", "entry_price")
    if base_spot is not None:
        return base_spot
    underlying = _position_underlying(position)
    ticker = ticker_by_underlying.get(underlying or "")
    return _ticker_base_spot(ticker) if ticker is not None else None


def _years_to_expiry(ticker: dict[str, Any]) -> float | None:
    years = _first_float(ticker, "yearsToExpiry", "years_to_expiry")
    if years is not None:
        return years
    dte_days = _first_float(ticker, "dteDays", "dte_days")
    if dte_days is not None:
        return dte_days / 365
    expiry_ms = _first_float(ticker, "expiryTsMs", "expiry_ts_ms")
    if expiry_ms is None:
        return 30 / 365
    return max((expiry_ms - int(time.time() * 1000)) / MS_PER_YEAR, 1 / 365)


def _option_type(ticker: dict[str, Any]) -> str | None:
    value = ticker.get("optionType") or ticker.get("option_type")
    if value:
        return option_type_code(value)
    instrument = _instrument_name(ticker)
    if not instrument:
        return None
    parsed = parse_option_instrument_name(instrument)
    return parsed.option_type if parsed is not None else None


def _instrument_name(value: dict[str, Any]) -> str | None:
    return extract_instrument_name(value)


def _position_underlying(position: dict[str, Any]) -> str | None:
    underlying = position.get("underlying")
    if underlying:
        return str(underlying)
    return instrument_underlying(_instrument_name(position))


def _normalize_metric(metric: str) -> str:
    metric = str(metric).lower()
    if metric not in GREEK_FIELDS:
        raise ValueError(f"Unsupported Greek metric: {metric}")
    return metric


def _first_float(source: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _to_float(source.get(key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 12)
