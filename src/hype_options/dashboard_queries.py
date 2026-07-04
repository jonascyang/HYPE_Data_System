from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from hype_options.dashboard_data import build_dashboard_payload
from hype_options.order_flow import get_order_flow_events

MS_PER_DAY = 86_400_000
DEFAULT_LOOKBACK_DAYS = 365
TENOR_ORDER = {"1D": 1, "1W": 2, "1M": 3, "3M": 4, "6M": 5}


def latest_snapshot_ts(conn) -> int | None:
    for table in ("derived_expiry_metrics", "derived_global_metrics", "derive_ticker_snapshots"):
        row = conn.execute(f"SELECT max(ts_ms) FROM {table}").fetchone()
        if row and row[0] is not None:
            return int(row[0])
    return None


def latest_order_flow_ts(conn) -> int | None:
    row = conn.execute("SELECT max(observed_at_ms) FROM derive_order_flow_events").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def build_dashboard_bootstrap(
    conn,
    *,
    selected_expiry: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    payload = build_dashboard_payload(conn, history_days=lookback_days)
    latest_ts_ms = payload.get("latestTsMs")
    expiry = selected_expiry or payload.get("defaultExpiry")
    vol_regime = get_vol_regime(conn, tenor="1M", lookback_days=lookback_days) if latest_ts_ms else _empty_vol_regime("1M", lookback_days)

    return {
        "snapshot": {
            "latestTsMs": latest_ts_ms,
            "snapshotLabel": payload.get("snapshotLabel"),
            "generatedAt": payload.get("generatedAt"),
            "source": payload.get("source"),
        },
        "summary": _summary_from_payload(payload, vol_regime),
        "selectedExpiry": expiry,
        "expiries": payload.get("expiryMetrics", []),
        "atmTerm": payload.get("atmIvTable", []),
        "skewFly": payload.get("skew25dTable", []),
        "ivSmile": get_iv_smile(conn, expiry, ts_ms=latest_ts_ms) if expiry and latest_ts_ms else [],
        "gexByStrike": get_gex_by_strike(conn, ts_ms=latest_ts_ms) if latest_ts_ms else [],
        "gexByExpiry": get_gex_by_expiry(conn, ts_ms=latest_ts_ms) if latest_ts_ms else [],
        "oiByStrike": get_oi_by_strike(conn, ts_ms=latest_ts_ms) if latest_ts_ms else [],
        "oiByExpiry": get_oi_by_expiry(conn, ts_ms=latest_ts_ms) if latest_ts_ms else [],
        "vrpHistory": payload.get("vrpHistory", []),
        "volRegime": vol_regime,
    }


def get_iv_smile(conn, expiry: str, *, ts_ms: int | None = None) -> list[dict[str, Any]]:
    ts_ms = ts_ms or latest_snapshot_ts(conn)
    if ts_ms is None:
        return []
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              strike, option_type, mark_iv, delta, gamma, vega, theta, rho,
              mark_price, mid_price, open_interest
            FROM derive_ticker_snapshots
            WHERE ts_ms = ?
              AND expiry_yyyymmdd = ?
              AND surface_quality != 'invalid'
              AND mark_iv IS NOT NULL
            ORDER BY strike, option_type
            """,
            (ts_ms, expiry),
        )
    )
    grouped: dict[float, dict[str, Any]] = {}
    for row in rows:
        strike = _num(row["strike"])
        point = grouped.setdefault(
            strike,
            {
                "strike": strike,
                "callIv": None,
                "putIv": None,
                "callDelta": None,
                "putDelta": None,
                "callGamma": None,
                "putGamma": None,
                "callVega": None,
                "putVega": None,
                "callTheta": None,
                "putTheta": None,
                "callRho": None,
                "putRho": None,
                "callPremium": None,
                "putPremium": None,
                "callOi": 0.0,
                "putOi": 0.0,
            },
        )
        if row["option_type"] == "C":
            point["callIv"] = _nullable_num(row["mark_iv"])
            point["callDelta"] = _nullable_num(row["delta"])
            point["callGamma"] = _nullable_num(row["gamma"])
            point["callVega"] = _nullable_num(row["vega"])
            point["callTheta"] = _nullable_num(row["theta"])
            point["callRho"] = _nullable_num(row["rho"])
            point["callPremium"] = _nullable_num(row["mark_price"] if row["mark_price"] is not None else row["mid_price"])
            point["callOi"] = _num(row["open_interest"])
        elif row["option_type"] == "P":
            point["putIv"] = _nullable_num(row["mark_iv"])
            point["putDelta"] = _nullable_num(row["delta"])
            point["putGamma"] = _nullable_num(row["gamma"])
            point["putVega"] = _nullable_num(row["vega"])
            point["putTheta"] = _nullable_num(row["theta"])
            point["putRho"] = _nullable_num(row["rho"])
            point["putPremium"] = _nullable_num(row["mark_price"] if row["mark_price"] is not None else row["mid_price"])
            point["putOi"] = _num(row["open_interest"])
    return list(grouped.values())


def get_gex_by_strike(conn, *, ts_ms: int | None = None) -> list[dict[str, Any]]:
    ts_ms = ts_ms or latest_snapshot_ts(conn)
    if ts_ms is None:
        return []
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              strike,
              SUM(COALESCE(call_gex, 0)) AS call_gex,
              SUM(COALESCE(put_gex, 0)) AS put_gex,
              SUM(COALESCE(net_gex, 0)) AS net_gex,
              SUM(COALESCE(abs_gex, 0)) AS abs_gex
            FROM derived_gex_by_strike
            WHERE ts_ms = ?
            GROUP BY strike
            ORDER BY strike
            """,
            (ts_ms,),
        )
    )
    return [
        {
            "strike": _num(row["strike"]),
            "callGex": _num(row["call_gex"]),
            "putGex": _num(row["put_gex"]),
            "netGex": _num(row["net_gex"]),
            "absGex": _num(row["abs_gex"]),
        }
        for row in rows
    ]


def get_gex_by_expiry(conn, *, ts_ms: int | None = None) -> list[dict[str, Any]]:
    ts_ms = ts_ms or latest_snapshot_ts(conn)
    if ts_ms is None:
        return []
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              expiry.expiry_yyyymmdd,
              strike_gex.strike,
              strike_gex.call_gex,
              strike_gex.put_gex,
              strike_gex.net_gex,
              strike_gex.abs_gex
            FROM derived_gex_by_strike AS strike_gex
            JOIN derived_expiry_metrics AS expiry
              ON expiry.ts_ms = strike_gex.ts_ms
             AND expiry.expiry_ts_ms = strike_gex.expiry_ts_ms
            WHERE strike_gex.ts_ms = ?
            ORDER BY strike_gex.expiry_ts_ms, strike_gex.strike
            """,
            (ts_ms,),
        )
    )
    return [
        {
            "expiry": row["expiry_yyyymmdd"],
            "strike": _num(row["strike"]),
            "callGex": _num(row["call_gex"]),
            "putGex": _num(row["put_gex"]),
            "netGex": _num(row["net_gex"]),
            "absGex": _num(row["abs_gex"]),
        }
        for row in rows
    ]


def get_oi_by_strike(conn, expiry: str | None = None, *, ts_ms: int | None = None) -> list[dict[str, Any]]:
    ts_ms = ts_ms or latest_snapshot_ts(conn)
    if ts_ms is None:
        return []
    expiry_filter = "AND expiry_yyyymmdd = ?" if expiry else ""
    params: tuple[Any, ...] = (ts_ms, expiry) if expiry else (ts_ms,)
    rows = _rows_as_dicts(
        conn.execute(
            f"""
            SELECT
              expiry_yyyymmdd,
              strike,
              SUM(CASE WHEN option_type = 'C' THEN COALESCE(open_interest, 0) ELSE 0 END) AS call_oi,
              SUM(CASE WHEN option_type = 'P' THEN COALESCE(open_interest, 0) ELSE 0 END) AS put_oi
            FROM derive_ticker_snapshots
            WHERE ts_ms = ?
              {expiry_filter}
            GROUP BY expiry_yyyymmdd, expiry_ts_ms, strike
            ORDER BY expiry_ts_ms, strike
            """,
            params,
        )
    )
    return [
        {
            "expiry": row["expiry_yyyymmdd"],
            "strike": _num(row["strike"]),
            "callOi": _num(row["call_oi"]),
            "putOi": _num(row["put_oi"]),
            "totalOi": _num(row["call_oi"]) + _num(row["put_oi"]),
        }
        for row in rows
    ]


def get_oi_by_expiry(conn, *, ts_ms: int | None = None) -> list[dict[str, Any]]:
    ts_ms = ts_ms or latest_snapshot_ts(conn)
    if ts_ms is None:
        return []
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT expiry_yyyymmdd, total_oi, call_oi, put_oi, total_volume, call_volume, put_volume
            FROM derived_expiry_metrics
            WHERE ts_ms = ?
            ORDER BY expiry_ts_ms
            """,
            (ts_ms,),
        )
    )
    return [
        {
            "expiry": row["expiry_yyyymmdd"],
            "totalOi": _num(row["total_oi"]),
            "callOi": _num(row["call_oi"]),
            "putOi": _num(row["put_oi"]),
            "totalVolume": _num(row["total_volume"]),
            "callVolume": _num(row["call_volume"]),
            "putVolume": _num(row["put_volume"]),
        }
        for row in rows
    ]


def get_vol_regime(conn, *, tenor: str = "1M", lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict[str, Any]:
    latest_ts_ms = latest_snapshot_ts(conn)
    if latest_ts_ms is None:
        return _empty_vol_regime(tenor, lookback_days)
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT ts_ms, atm_iv
            FROM derived_atm_term_metrics
            WHERE tenor = ?
              AND ts_ms >= ?
              AND ts_ms <= ?
              AND atm_iv IS NOT NULL
            ORDER BY ts_ms
            """,
            (tenor, start_ts_ms, latest_ts_ms),
        )
    )
    values = [_num(row["atm_iv"]) for row in rows]
    if not values:
        return _empty_vol_regime(tenor, lookback_days, latest_ts_ms=latest_ts_ms)
    current = values[-1]
    min_iv = min(values)
    max_iv = max(values)
    rank = ((current - min_iv) / (max_iv - min_iv) * 100) if max_iv > min_iv else None
    percentile = sum(1 for value in values if value <= current) / len(values) * 100
    return {
        "tenor": tenor,
        "lookbackDays": lookback_days,
        "latestTsMs": latest_ts_ms,
        "currentAtmIv": current,
        "minAtmIv": min_iv,
        "maxAtmIv": max_iv,
        "ivRank": _round(rank),
        "ivPercentile": _round(percentile),
        "sampleCount": len(values),
    }


def build_panel_payload(conn, panel: str, params: dict[str, Any]) -> Any:
    expiry = params.get("expiry")
    if panel == "ivSmile" and expiry:
        return get_iv_smile(conn, str(expiry))
    if panel == "gexByStrike":
        return get_gex_by_strike(conn)
    if panel == "gexByExpiry":
        return get_gex_by_expiry(conn)
    if panel == "oiByStrike" and expiry:
        return get_oi_by_strike(conn, str(expiry))
    if panel == "oiByExpiry":
        return get_oi_by_expiry(conn)
    if panel == "volRegime":
        return get_vol_regime(
            conn,
            tenor=str(params.get("tenor") or "1M"),
            lookback_days=int(params.get("lookbackDays") or DEFAULT_LOOKBACK_DAYS),
        )
    if panel in {"summary", "atmTerm", "skewFly", "vrpHistory"}:
        bootstrap = build_dashboard_bootstrap(conn)
        return bootstrap.get(panel)
    if panel == "orderFlow":
        return get_order_flow_events(
            conn,
            execution_type=_optional_text(params.get("executionType")),
            leg_structure=_optional_text(params.get("legStructure")),
            option_mix=_optional_text(params.get("optionMix")),
            side=_optional_text(params.get("side")),
            order_type=_optional_text(params.get("orderType")),
            time_in_force=_optional_text(params.get("timeInForce")),
            min_amount=_optional_float(params.get("minAmount")),
            min_premium_usd=_optional_float(params.get("minPremiumUsd")),
            limit=_optional_int(params.get("limit"), default=100),
        )
    raise ValueError(f"Unsupported panel: {panel}")


def _summary_from_payload(payload: dict[str, Any], vol_regime: dict[str, Any]) -> dict[str, Any]:
    global_metrics = payload.get("globalMetrics") or {}
    atm_by_tenor = {
        row.get("tenor"): row.get("atmIv")
        for row in payload.get("atmIvTable", [])
        if row.get("tenor")
    }
    return {
        "spotPrice": global_metrics.get("spotPrice"),
        "spotChange24hPct": global_metrics.get("spotChange24hPct"),
        "totalOptionOi": global_metrics.get("totalOptionOi"),
        "totalOptionVolume": global_metrics.get("totalOptionVolume"),
        "putCallVolumeRatio": global_metrics.get("putCallVolumeRatio"),
        "netGex": global_metrics.get("netGex"),
        "absGex": global_metrics.get("absGex"),
        "vrp7d": global_metrics.get("vrp7d"),
        "vrp30d": global_metrics.get("vrp30d"),
        "atmIv": {tenor: atm_by_tenor.get(tenor) for tenor in sorted(TENOR_ORDER, key=TENOR_ORDER.get)},
        "ivRank": vol_regime.get("ivRank"),
        "ivPercentile": vol_regime.get("ivPercentile"),
        "volRegimeTenor": vol_regime.get("tenor"),
        "volRegimeLookbackDays": vol_regime.get("lookbackDays"),
    }


def _empty_vol_regime(tenor: str, lookback_days: int, *, latest_ts_ms: int | None = None) -> dict[str, Any]:
    return {
        "tenor": tenor,
        "lookbackDays": lookback_days,
        "latestTsMs": latest_ts_ms,
        "currentAtmIv": None,
        "minAtmIv": None,
        "maxAtmIv": None,
        "ivRank": None,
        "ivPercentile": None,
        "sampleCount": 0,
    }


def format_timestamp(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S UTC+08")


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _nullable_num(value: Any) -> float | None:
    return None if value is None else float(value)


def _num(value: Any) -> float:
    return 0.0 if value is None else float(value)


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
