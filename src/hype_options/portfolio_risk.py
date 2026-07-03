from __future__ import annotations

from typing import Any

from hype_options.greeks import (
    GREEK_FIELDS,
    build_portfolio_curve_bundle,
    option_positions,
    portfolio_positions,
    position_underlyings,
    sum_position_greeks,
)
from hype_options.instruments import extract_instrument_name, parse_option_instrument_name
from hype_options.strategy_templates import simulate_strategy


SINGLE_ASSET_ERROR = "Select a single asset to calculate Greeks and payoff"


def portfolio_option_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return option_positions(portfolio_positions(positions))


def validate_single_asset_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_positions = portfolio_positions(positions)
    underlyings = position_underlyings(risk_positions)
    if len(underlyings) > 1:
        raise ValueError(SINGLE_ASSET_ERROR)
    return risk_positions


def missing_ticker_requests(
    positions: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
) -> set[tuple[str, str]]:
    requests: set[tuple[str, str]] = set()
    for position in portfolio_option_positions(positions):
        instrument = extract_instrument_name(position)
        if not instrument:
            continue
        ticker = ticker_by_instrument.get(instrument)
        if ticker is not None and ticker_has_curve_inputs(ticker):
            continue
        parsed = parse_option_instrument_name(instrument)
        if parsed is not None:
            requests.add((parsed.currency, parsed.expiry))
    return requests


def ticker_has_curve_inputs(ticker: dict[str, Any]) -> bool:
    base_price = _first_number(ticker, "forwardPrice", "forward_price", "indexPrice", "index_price")
    return (
        base_price is not None
        and _first_number(ticker, "strike") is not None
        and _first_number(ticker, "markIv", "mark_iv") is not None
    )


def evaluate_portfolio_positions(
    positions: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
    metric: str = "delta",
) -> dict[str, Any]:
    risk_positions = validate_single_asset_positions(positions)
    totals = sum_position_greeks(risk_positions)
    curve_bundle = build_portfolio_curve_bundle(risk_positions, ticker_by_instrument, metric)
    curve = curve_bundle["curve"]
    return {
        "summary": greek_summary(totals, position_count=len(risk_positions)),
        "curve": curve_response(curve),
        "curves": curves_response(curve_bundle["curves"]),
        "payoffCurve": payoff_curve_response(curve),
        "unavailableInstruments": curve.get("unavailableInstruments", []),
    }


def evaluate_strategy_legs(
    legs: list[dict[str, Any]],
    ticker_by_instrument: dict[str, dict[str, Any]],
    metric: str = "delta",
) -> dict[str, Any]:
    simulation = simulate_strategy(legs, ticker_by_instrument)
    return strategy_simulation_response(simulation, ticker_by_instrument, metric)


def strategy_simulation_response(
    simulation: dict[str, Any],
    ticker_by_instrument: dict[str, dict[str, Any]],
    metric: str = "delta",
) -> dict[str, Any]:
    totals = simulation.get("totals", {})
    legs = [leg_response(leg) for leg in simulation.get("legs", [])]
    try:
        curve_bundle = build_portfolio_curve_bundle(simulation.get("legs", []), ticker_by_instrument, metric)
        curve = curve_bundle["curve"]
        curve_payload = curve_response(curve)
        curves_payload = curves_response(curve_bundle["curves"])
        payoff_curve_payload = payoff_curve_response(curve)
    except ValueError:
        curve_payload = None
        curves_payload = {}
        payoff_curve_payload = None
    return {
        "premium": totals.get("premium"),
        "greeks": greek_summary(totals, position_count=len(legs)),
        "curve": curve_payload,
        "curves": curves_payload,
        "payoffCurve": payoff_curve_payload,
        "legs": legs,
    }


def leg_response(leg: dict[str, Any]) -> dict[str, Any]:
    return {
        "instrumentName": leg.get("instrumentName"),
        "optionType": _option_name(leg.get("optionType") or leg.get("option_type")),
        "expiry": leg.get("expiry"),
        "strike": leg.get("strike"),
        "side": leg.get("side"),
        "quantity": leg.get("quantity"),
        "markPrice": leg.get("markPrice"),
        "premium": leg.get("premium"),
    }


def greek_summary(totals: dict[str, Any], *, position_count: int | None = None) -> dict[str, Any]:
    summary = {
        "totalDelta": totals.get("delta"),
        "totalGamma": totals.get("gamma"),
        "totalVega": totals.get("vega"),
        "totalTheta": totals.get("theta"),
    }
    if position_count is not None:
        summary["positionCount"] = position_count
    return summary


def curve_response(curve: dict[str, Any] | None) -> dict[str, Any] | None:
    if curve is None:
        return None
    return {
        "metric": curve.get("metric"),
        "points": curve.get("points", []),
        "scenarioRows": curve.get("scenarioTable", []),
        "unavailableInstruments": curve.get("unavailableInstruments", []),
    }


def curves_response(curves: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    return {metric: curve_response(curve) for metric, curve in curves.items() if metric in GREEK_FIELDS}


def payoff_curve_response(curve: dict[str, Any] | None) -> dict[str, Any] | None:
    if curve is None:
        return None
    return {
        "points": curve.get("payoffPoints", []),
        "scenarioRows": curve.get("payoffScenarioTable", []),
        "unavailableInstruments": curve.get("payoffUnavailableInstruments", []),
    }


def _option_name(value: Any) -> str | None:
    text = str(value or "").upper()
    if text.startswith("C"):
        return "call"
    if text.startswith("P"):
        return "put"
    return None


def _first_number(source: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None
