from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence

from hype_options.models import AtmTermMetric, ExpiryMetrics, GexByStrike, GlobalMetrics
from hype_options.models import TickerSnapshot

ATM_TERM_TENORS = [
    ("1D", 1),
    ("1W", 7),
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
]


def interpolate_iv_at_delta(points: Sequence[dict], target_delta: float) -> float | None:
    valid = sorted(
        (point for point in points if point.get("delta") is not None and point.get("iv") is not None),
        key=lambda point: point["delta"],
    )
    return _linear_interpolate(valid, "delta", "iv", target_delta)


def interpolate_atm_iv(points: Sequence[dict], forward_price: float) -> float | None:
    valid = sorted(
        (
            point
            for point in points
            if point.get("strike") is not None and point.get("iv") is not None
        ),
        key=lambda point: point["strike"],
    )
    return _linear_interpolate(valid, "strike", "iv", forward_price)


def compute_25d_skew(put_25d_iv: float, call_25d_iv: float) -> float:
    return put_25d_iv - call_25d_iv


def compute_25d_fly(put_25d_iv: float, call_25d_iv: float, atm_iv: float) -> float:
    return ((put_25d_iv + call_25d_iv) / 2) - atm_iv


def compute_gex(
    *,
    gamma: float,
    open_interest: float,
    spot_price: float,
    option_type: str,
    contract_multiplier: float = 1,
) -> float:
    value = gamma * open_interest * contract_multiplier * spot_price * spot_price
    return value if option_type == "C" else -value


def compute_max_pain(rows: Sequence[dict]) -> float | None:
    strikes = sorted({float(row["strike"]) for row in rows if row.get("strike") is not None})
    if not strikes:
        return None

    best_strike = None
    best_payoff = None
    for settlement in strikes:
        payoff = 0.0
        for row in rows:
            strike = float(row["strike"])
            oi = float(row.get("open_interest") or 0)
            if row.get("option_type") == "C":
                payoff += max(0.0, settlement - strike) * oi
            elif row.get("option_type") == "P":
                payoff += max(0.0, strike - settlement) * oi
        if best_payoff is None or payoff < best_payoff:
            best_payoff = payoff
            best_strike = settlement
    return best_strike


def compute_gex_by_strike(
    rows: Sequence[TickerSnapshot],
    *,
    ts_ms: int,
    spot_price: float,
) -> list[GexByStrike]:
    grouped: dict[tuple[int, float], list[TickerSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[(row.expiry_ts_ms, row.strike)].append(row)

    strike_rows: list[GexByStrike] = []
    for (expiry_ts_ms, strike), group_rows in sorted(grouped.items()):
        call_gex = 0.0
        put_gex = 0.0
        call_oi = 0.0
        put_oi = 0.0
        for row in group_rows:
            gex = compute_gex(
                gamma=float(row.gamma or 0),
                open_interest=float(row.open_interest or 0),
                spot_price=spot_price,
                option_type=row.option_type,
            )
            if row.option_type == "C":
                call_gex += gex
                call_oi += float(row.open_interest or 0)
            elif row.option_type == "P":
                put_gex += gex
                put_oi += float(row.open_interest or 0)
        strike_rows.append(
            GexByStrike(
                ts_ms=ts_ms,
                expiry_ts_ms=expiry_ts_ms,
                strike=strike,
                call_gex=call_gex,
                put_gex=put_gex,
                net_gex=call_gex + put_gex,
                abs_gex=abs(call_gex) + abs(put_gex),
                call_oi=call_oi,
                put_oi=put_oi,
            )
        )
    return strike_rows


def compute_global_metrics(
    *,
    expiry_metrics: Sequence[ExpiryMetrics],
    price_points: Sequence[dict],
    ts_ms: int,
    spot_price: float | None,
) -> GlobalMetrics | None:
    if not expiry_metrics and spot_price is None:
        return None

    atm_iv_7d = _interpolate_term_metric(expiry_metrics, 7, "atm_iv")
    atm_iv_30d = _interpolate_term_metric(expiry_metrics, 30, "atm_iv")
    atm_iv_60d = _interpolate_term_metric(expiry_metrics, 60, "atm_iv")
    atm_iv_90d = _interpolate_term_metric(expiry_metrics, 90, "atm_iv")

    rv_1d = annualized_realized_vol_from_points(price_points, end_ts_ms=ts_ms, window_days=1)
    rv_7d = annualized_realized_vol_from_points(price_points, end_ts_ms=ts_ms, window_days=7)
    rv_14d = annualized_realized_vol_from_points(price_points, end_ts_ms=ts_ms, window_days=14)
    rv_30d = annualized_realized_vol_from_points(price_points, end_ts_ms=ts_ms, window_days=30)

    call_volume = sum(metric.call_volume for metric in expiry_metrics)
    put_volume = sum(metric.put_volume for metric in expiry_metrics)
    net_gex = sum(metric.net_gex for metric in expiry_metrics)
    abs_gex = sum(metric.abs_gex for metric in expiry_metrics)

    return GlobalMetrics(
        ts_ms=ts_ms,
        spot_price=spot_price,
        rv_1d=rv_1d,
        rv_7d=rv_7d,
        rv_14d=rv_14d,
        rv_30d=rv_30d,
        atm_iv_7d=atm_iv_7d,
        atm_iv_30d=atm_iv_30d,
        atm_iv_60d=atm_iv_60d,
        atm_iv_90d=atm_iv_90d,
        vrp_7d=atm_iv_7d - rv_7d if atm_iv_7d is not None and rv_7d is not None else None,
        vrp_30d=atm_iv_30d - rv_30d if atm_iv_30d is not None and rv_30d is not None else None,
        total_option_oi=sum(metric.total_oi for metric in expiry_metrics),
        total_option_volume=sum(metric.total_volume for metric in expiry_metrics),
        call_volume=call_volume,
        put_volume=put_volume,
        put_call_volume_ratio=_safe_ratio(put_volume, call_volume),
        total_gex=sum(metric.total_gex for metric in expiry_metrics),
        net_gex=net_gex,
        abs_gex=abs_gex,
    )


def compute_atm_term_metrics(
    expiry_metrics: Sequence[ExpiryMetrics],
    *,
    ts_ms: int,
) -> list[AtmTermMetric]:
    points = sorted(
        (
            metric
            for metric in expiry_metrics
            if metric.dte_days is not None and metric.atm_iv is not None
        ),
        key=lambda metric: float(metric.dte_days),
    )
    return [
        _compute_atm_term_metric(points, ts_ms=ts_ms, tenor=tenor, target_dte_days=target_dte)
        for tenor, target_dte in ATM_TERM_TENORS
    ]


def _compute_atm_term_metric(
    points: Sequence[ExpiryMetrics],
    *,
    ts_ms: int,
    tenor: str,
    target_dte_days: float,
) -> AtmTermMetric:
    if not points:
        return AtmTermMetric(
            ts_ms=ts_ms,
            tenor=tenor,
            target_dte_days=target_dte_days,
            atm_iv=None,
            method="unavailable",
            left_expiry_yyyymmdd=None,
            left_dte_days=None,
            left_atm_iv=None,
            right_expiry_yyyymmdd=None,
            right_dte_days=None,
            right_atm_iv=None,
        )

    if target_dte_days <= float(points[0].dte_days):
        return _atm_term_row(
            ts_ms=ts_ms,
            tenor=tenor,
            target_dte_days=target_dte_days,
            left=points[0],
            right=points[0],
            atm_iv=points[0].atm_iv,
            method="nearest_front_expiry",
        )
    if target_dte_days >= float(points[-1].dte_days):
        return _atm_term_row(
            ts_ms=ts_ms,
            tenor=tenor,
            target_dte_days=target_dte_days,
            left=points[-1],
            right=points[-1],
            atm_iv=points[-1].atm_iv,
            method="nearest_back_expiry",
        )

    for left, right in zip(points, points[1:]):
        left_dte = float(left.dte_days)
        right_dte = float(right.dte_days)
        if left_dte <= target_dte_days <= right_dte:
            if right_dte == left_dte:
                atm_iv = left.atm_iv
            else:
                weight = (target_dte_days - left_dte) / (right_dte - left_dte)
                atm_iv = float(left.atm_iv) + weight * (float(right.atm_iv) - float(left.atm_iv))
            return _atm_term_row(
                ts_ms=ts_ms,
                tenor=tenor,
                target_dte_days=target_dte_days,
                left=left,
                right=right,
                atm_iv=atm_iv,
                method="linear_interpolation",
            )

    return _atm_term_row(
        ts_ms=ts_ms,
        tenor=tenor,
        target_dte_days=target_dte_days,
        left=points[-1],
        right=points[-1],
        atm_iv=points[-1].atm_iv,
        method="nearest_back_expiry",
    )


def _atm_term_row(
    *,
    ts_ms: int,
    tenor: str,
    target_dte_days: float,
    left: ExpiryMetrics,
    right: ExpiryMetrics,
    atm_iv: float | None,
    method: str,
) -> AtmTermMetric:
    return AtmTermMetric(
        ts_ms=ts_ms,
        tenor=tenor,
        target_dte_days=target_dte_days,
        atm_iv=atm_iv,
        method=method,
        left_expiry_yyyymmdd=left.expiry_yyyymmdd,
        left_dte_days=left.dte_days,
        left_atm_iv=left.atm_iv,
        right_expiry_yyyymmdd=right.expiry_yyyymmdd,
        right_dte_days=right.dte_days,
        right_atm_iv=right.atm_iv,
    )


def annualized_realized_vol_from_points(
    price_points: Sequence[dict],
    *,
    end_ts_ms: int,
    window_days: int,
) -> float | None:
    start_ts_ms = end_ts_ms - window_days * 86_400_000
    valid = sorted(
        (
            {"ts_ms": int(point["ts_ms"]), "price": float(point["price"])}
            for point in price_points
            if point.get("ts_ms") is not None
            and point.get("price") is not None
            and start_ts_ms <= int(point["ts_ms"]) <= end_ts_ms
            and float(point["price"]) > 0
        ),
        key=lambda point: point["ts_ms"],
    )
    if len(valid) < 2:
        return None

    squared_returns = []
    elapsed_ms = valid[-1]["ts_ms"] - valid[0]["ts_ms"]
    if elapsed_ms <= 0:
        return None
    for prev, curr in zip(valid, valid[1:]):
        if curr["ts_ms"] <= prev["ts_ms"]:
            continue
        squared_returns.append(math.log(curr["price"] / prev["price"]) ** 2)
    if not squared_returns:
        return None
    elapsed_years = elapsed_ms / (365 * 86_400_000)
    return math.sqrt(sum(squared_returns) / elapsed_years)


def compute_expiry_metrics(
    rows: Sequence[TickerSnapshot],
    *,
    ts_ms: int,
    spot_price: float,
) -> list[ExpiryMetrics]:
    grouped: dict[tuple[int, str], list[TickerSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[(row.expiry_ts_ms, row.expiry_yyyymmdd)].append(row)

    metrics: list[ExpiryMetrics] = []
    for (expiry_ts_ms, expiry_yyyymmdd), expiry_rows in sorted(grouped.items()):
        surface_rows = [
            row
            for row in expiry_rows
            if row.surface_quality != "invalid" and row.mark_iv is not None and row.delta is not None
        ]
        all_points = [
            {"strike": row.strike, "iv": row.mark_iv}
            for row in surface_rows
            if row.mark_iv is not None
        ]
        call_points = [
            {"delta": row.delta, "iv": row.mark_iv}
            for row in surface_rows
            if row.option_type == "C" and row.delta is not None and row.mark_iv is not None
        ]
        put_points = [
            {"delta": row.delta, "iv": row.mark_iv}
            for row in surface_rows
            if row.option_type == "P" and row.delta is not None and row.mark_iv is not None
        ]

        forward_price = _first_not_none(row.forward_price for row in expiry_rows) or spot_price
        atm_iv = interpolate_atm_iv(all_points, forward_price=forward_price)
        atm_strike = _nearest_strike(expiry_rows, forward_price)
        call_25d_iv = interpolate_iv_at_delta(call_points, 0.25)
        put_25d_iv = interpolate_iv_at_delta(put_points, -0.25)
        skew_25d = (
            compute_25d_skew(put_25d_iv=put_25d_iv, call_25d_iv=call_25d_iv)
            if put_25d_iv is not None and call_25d_iv is not None
            else None
        )
        fly_25d = (
            compute_25d_fly(put_25d_iv=put_25d_iv, call_25d_iv=call_25d_iv, atm_iv=atm_iv)
            if put_25d_iv is not None and call_25d_iv is not None and atm_iv is not None
            else None
        )

        call_rows = [row for row in expiry_rows if row.option_type == "C"]
        put_rows = [row for row in expiry_rows if row.option_type == "P"]
        call_oi = sum(float(row.open_interest or 0) for row in call_rows)
        put_oi = sum(float(row.open_interest or 0) for row in put_rows)
        total_oi = call_oi + put_oi
        call_volume = sum(float(row.volume or 0) for row in call_rows)
        put_volume = sum(float(row.volume or 0) for row in put_rows)
        total_volume = call_volume + put_volume

        gex_values = [
            compute_gex(
                gamma=float(row.gamma or 0),
                open_interest=float(row.open_interest or 0),
                spot_price=spot_price,
                option_type=row.option_type,
            )
            for row in expiry_rows
        ]
        net_gex = sum(gex_values)
        abs_gex = sum(abs(value) for value in gex_values)
        dte_days = (expiry_ts_ms - ts_ms) / 86_400_000

        metrics.append(
            ExpiryMetrics(
                ts_ms=ts_ms,
                expiry_ts_ms=expiry_ts_ms,
                expiry_yyyymmdd=expiry_yyyymmdd,
                dte_days=dte_days,
                atm_iv=atm_iv,
                atm_strike=atm_strike,
                call_25d_iv=call_25d_iv,
                put_25d_iv=put_25d_iv,
                skew_25d=skew_25d,
                fly_25d=fly_25d,
                total_oi=total_oi,
                call_oi=call_oi,
                put_oi=put_oi,
                put_call_oi_ratio=_safe_ratio(put_oi, call_oi),
                total_volume=total_volume,
                call_volume=call_volume,
                put_volume=put_volume,
                put_call_volume_ratio=_safe_ratio(put_volume, call_volume),
                max_pain_price=compute_max_pain([_ticker_dict(row) for row in expiry_rows]),
                total_gex=net_gex,
                net_gex=net_gex,
                abs_gex=abs_gex,
                model_point_count=sum(1 for row in expiry_rows if row.surface_quality == "model"),
                tradable_point_count=sum(1 for row in expiry_rows if row.surface_quality == "tradable"),
            )
        )
    return metrics


def _linear_interpolate(
    points: Sequence[dict],
    x_key: str,
    y_key: str,
    target_x: float,
) -> float | None:
    if not points:
        return None
    if target_x <= points[0][x_key]:
        return points[0][y_key]
    if target_x >= points[-1][x_key]:
        return points[-1][y_key]

    for left, right in zip(points, points[1:]):
        if left[x_key] <= target_x <= right[x_key]:
            span = right[x_key] - left[x_key]
            if span == 0:
                return left[y_key]
            weight = (target_x - left[x_key]) / span
            return left[y_key] + weight * (right[y_key] - left[y_key])
    return None


def _first_not_none(values):
    for value in values:
        if value is not None:
            return value
    return None


def _nearest_strike(rows: Sequence[TickerSnapshot], price: float) -> float | None:
    strikes = [row.strike for row in rows if row.strike is not None]
    if not strikes:
        return None
    return min(strikes, key=lambda strike: abs(strike - price))


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _interpolate_term_metric(
    metrics: Sequence[ExpiryMetrics],
    target_dte_days: float,
    field: str,
) -> float | None:
    points = [
        {"dte_days": metric.dte_days, "value": getattr(metric, field)}
        for metric in metrics
        if metric.dte_days is not None and getattr(metric, field) is not None
    ]
    valid = sorted(points, key=lambda point: point["dte_days"])
    return _linear_interpolate(valid, "dte_days", "value", target_dte_days)


def _ticker_dict(row: TickerSnapshot) -> dict:
    return {
        "strike": row.strike,
        "option_type": row.option_type,
        "open_interest": row.open_interest,
    }
