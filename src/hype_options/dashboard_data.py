from __future__ import annotations

import json
import math
from bisect import bisect_left, bisect_right
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TENORS = [
    ("1D", 1),
    ("1W", 7),
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
]
ATM_CHANGE_OFFSETS = {
    "chg1d": 1,
    "chg2d": 2,
    "chg1w": 7,
    "chg2w": 14,
    "chg1m": 30,
}
VRP_PERIODS = ("1D", "3D", "7D", "30D")
SECONDS_PER_DAY = 86_400
MS_PER_DAY = SECONDS_PER_DAY * 1000
CHANGE_LOOKUP_TOLERANCE_MS = 10 * 60 * 1000


def build_dashboard_payload(conn, *, history_days: int = 90, max_history_points: int = 720) -> dict:
    latest_ts_ms = _latest_snapshot_ts(conn)
    if latest_ts_ms is None:
        return _empty_payload()

    expiry_metrics = _expiry_metrics_at(conn, latest_ts_ms)
    global_metrics = _global_metrics_at(conn, latest_ts_ms)
    gex_by_strike = _gex_by_strike_at(conn, latest_ts_ms)
    iv_curve = _iv_curve_at(conn, latest_ts_ms)
    default_expiry = _default_expiry(expiry_metrics)
    global_history = _global_history(conn, latest_ts_ms, history_days=history_days)
    price_history = _price_history(conn, latest_ts_ms, history_days=history_days + 31)

    payload = {
        "version": 1,
        "source": "turso",
        "generatedAt": _format_timestamp(int(datetime.now(UTC).timestamp() * 1000)),
        "snapshotLabel": _format_timestamp(latest_ts_ms),
        "latestTsMs": latest_ts_ms,
        "defaultExpiry": default_expiry,
        "globalMetrics": _serialize_global_metrics(global_metrics, latest_ts_ms),
        "atmIvTable": _atm_iv_table(conn, latest_ts_ms, expiry_metrics, global_metrics),
        "skew25dTable": _skew_25d_table(conn, latest_ts_ms, expiry_metrics),
        "expiryMetrics": [_serialize_expiry_metric(row) for row in expiry_metrics],
        "ivCurve": iv_curve,
        "gexByStrike": gex_by_strike,
        "vrpHistory": _vrp_history(
            global_history,
            price_history,
            max_history_points=max_history_points,
        ),
    }
    return payload


def write_dashboard_payload(conn, output_path: Path, *, history_days: int = 90) -> dict:
    payload = build_dashboard_payload(conn, history_days=history_days)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _empty_payload() -> dict:
    return {
        "version": 1,
        "source": "turso",
        "generatedAt": _format_timestamp(int(datetime.now(UTC).timestamp() * 1000)),
        "snapshotLabel": None,
        "latestTsMs": None,
        "defaultExpiry": None,
        "globalMetrics": {},
        "atmIvTable": [],
        "skew25dTable": [],
        "expiryMetrics": [],
        "ivCurve": [],
        "gexByStrike": [],
        "vrpHistory": [],
    }


def _latest_snapshot_ts(conn) -> int | None:
    row = conn.execute("SELECT max(ts_ms) FROM derived_expiry_metrics").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _expiry_metrics_at(conn, ts_ms: int) -> list[dict]:
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT
              ts_ms,
              expiry_ts_ms,
              expiry_yyyymmdd,
              dte_days,
              atm_iv,
              atm_strike,
              call_25d_iv,
              put_25d_iv,
              skew_25d,
              fly_25d,
              total_oi,
              call_oi,
              put_oi,
              put_call_oi_ratio,
              total_volume,
              call_volume,
              put_volume,
              put_call_volume_ratio,
              max_pain_price,
              net_gex,
              abs_gex,
              tradable_point_count,
              model_point_count
            FROM derived_expiry_metrics
            WHERE ts_ms = ?
            ORDER BY expiry_ts_ms
            """,
            (ts_ms,),
        )
    )


def _global_metrics_at(conn, ts_ms: int) -> dict | None:
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              ts_ms,
              spot_price,
              rv_1d,
              rv_7d,
              rv_14d,
              rv_30d,
              atm_iv_7d,
              atm_iv_30d,
              atm_iv_60d,
              atm_iv_90d,
              vrp_7d,
              vrp_30d,
              total_option_oi,
              total_option_volume,
              call_volume,
              put_volume,
              put_call_volume_ratio,
              net_gex,
              abs_gex
            FROM derived_global_metrics
            WHERE ts_ms = ?
            """,
            (ts_ms,),
        )
    )
    return rows[0] if rows else None


def _gex_by_strike_at(conn, ts_ms: int) -> list[dict]:
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              expiry.expiry_yyyymmdd,
              strike_gex.strike,
              strike_gex.call_gex,
              strike_gex.put_gex,
              strike_gex.net_gex,
              strike_gex.abs_gex,
              strike_gex.call_oi,
              strike_gex.put_oi
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
            "callOi": _num(row["call_oi"]),
            "putOi": _num(row["put_oi"]),
        }
        for row in rows
    ]


def _iv_curve_at(conn, ts_ms: int) -> list[dict]:
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT
              expiry_yyyymmdd,
              option_type,
              strike,
              delta,
              mark_iv AS iv,
              open_interest
            FROM derive_ticker_snapshots
            WHERE ts_ms = ?
              AND surface_quality != 'invalid'
              AND mark_iv IS NOT NULL
            ORDER BY expiry_ts_ms, strike, option_type
            """,
            (ts_ms,),
        )
    )
    grouped: dict[tuple[str, float], dict] = {}
    for row in rows:
        key = (row["expiry_yyyymmdd"], float(row["strike"]))
        point = grouped.setdefault(
            key,
            {
                "expiry": row["expiry_yyyymmdd"],
                "strike": _num(row["strike"]),
                "callIv": None,
                "putIv": None,
                "callDelta": None,
                "putDelta": None,
                "callOi": 0.0,
                "putOi": 0.0,
            },
        )
        if row["option_type"] == "C":
            point["callIv"] = _nullable_num(row["iv"])
            point["callDelta"] = _nullable_num(row["delta"])
            point["callOi"] = _num(row["open_interest"])
        elif row["option_type"] == "P":
            point["putIv"] = _nullable_num(row["iv"])
            point["putDelta"] = _nullable_num(row["delta"])
            point["putOi"] = _num(row["open_interest"])
    return list(grouped.values())


def _global_history(conn, latest_ts_ms: int, *, history_days: int) -> list[dict]:
    start_ts_ms = latest_ts_ms - history_days * MS_PER_DAY
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT
              ts_ms,
              rv_1d,
              rv_7d,
              rv_30d,
              atm_iv_7d,
              atm_iv_30d
            FROM derived_global_metrics
            WHERE ts_ms >= ? AND ts_ms <= ?
            ORDER BY ts_ms
            """,
            (start_ts_ms, latest_ts_ms),
        )
    )


def _price_history(conn, latest_ts_ms: int, *, history_days: int) -> list[dict]:
    start_ts_ms = latest_ts_ms - history_days * MS_PER_DAY
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT ts_ms, price
            FROM hype_price_snapshots
            WHERE ts_ms >= ? AND ts_ms <= ?
            ORDER BY ts_ms
            """,
            (start_ts_ms, latest_ts_ms),
        )
    )


def _serialize_global_metrics(row: dict | None, latest_ts_ms: int) -> dict:
    row = row or {"ts_ms": latest_ts_ms}
    return {
        "tsMs": latest_ts_ms,
        "spotPrice": _nullable_num(row.get("spot_price")),
        "rv1d": _nullable_num(row.get("rv_1d")),
        "rv7d": _nullable_num(row.get("rv_7d")),
        "rv14d": _nullable_num(row.get("rv_14d")),
        "rv30d": _nullable_num(row.get("rv_30d")),
        "atmIv7d": _nullable_num(row.get("atm_iv_7d")),
        "atmIv30d": _nullable_num(row.get("atm_iv_30d")),
        "atmIv60d": _nullable_num(row.get("atm_iv_60d")),
        "atmIv90d": _nullable_num(row.get("atm_iv_90d")),
        "vrp7d": _nullable_num(row.get("vrp_7d")),
        "vrp30d": _nullable_num(row.get("vrp_30d")),
        "totalOptionOi": _num(row.get("total_option_oi")),
        "totalOptionVolume": _num(row.get("total_option_volume")),
        "callVolume": _num(row.get("call_volume")),
        "putVolume": _num(row.get("put_volume")),
        "putCallVolumeRatio": _nullable_num(row.get("put_call_volume_ratio")),
        "netGex": _num(row.get("net_gex")),
        "absGex": _num(row.get("abs_gex")),
    }


def _serialize_expiry_metric(row: dict) -> dict:
    return {
        "expiry": row["expiry_yyyymmdd"],
        "dte": _nullable_num(row["dte_days"]),
        "atmIv": _nullable_num(row["atm_iv"]),
        "atmStrike": _nullable_num(row["atm_strike"]),
        "call25dIv": _nullable_num(row["call_25d_iv"]),
        "put25dIv": _nullable_num(row["put_25d_iv"]),
        "skew25d": _nullable_num(row["skew_25d"]),
        "fly25d": _nullable_num(row["fly_25d"]),
        "totalOi": _num(row["total_oi"]),
        "callOi": _num(row["call_oi"]),
        "putOi": _num(row["put_oi"]),
        "totalVolume": _num(row["total_volume"]),
        "callVolume": _num(row["call_volume"]),
        "putVolume": _num(row["put_volume"]),
        "maxPain": _nullable_num(row["max_pain_price"]),
        "netGex": _num(row["net_gex"]),
        "absGex": _num(row["abs_gex"]),
        "tradablePoints": int(row["tradable_point_count"] or 0),
        "modelPoints": int(row["model_point_count"] or 0),
    }


def _atm_iv_table(
    conn,
    latest_ts_ms: int,
    expiry_metrics: list[dict],
    global_metrics: dict | None,
) -> list[dict]:
    term_rows = _atm_term_metrics_at(conn, latest_ts_ms)
    if term_rows:
        return _atm_iv_table_from_terms(conn, latest_ts_ms, term_rows, global_metrics)
    return _atm_iv_table_from_expiry_metrics(conn, latest_ts_ms, expiry_metrics, global_metrics)


def _atm_iv_table_from_terms(
    conn,
    latest_ts_ms: int,
    term_rows: list[dict],
    global_metrics: dict | None,
) -> list[dict]:
    current_by_tenor = {row["tenor"]: row for row in term_rows}
    rv_7d = _nullable_num((global_metrics or {}).get("rv_7d"))
    rows = []
    for tenor, _target_dte in TENORS:
        term_row = current_by_tenor.get(tenor)
        atm_iv = _nullable_num(term_row.get("atm_iv")) if term_row else None
        data = {
            "tenor": tenor,
            "atmIv": atm_iv,
            "chg1d": None,
            "chg2d": None,
            "chg1w": None,
            "chg2w": None,
            "chg1m": None,
            "vrp1w": atm_iv - rv_7d if tenor == "1W" and atm_iv is not None and rv_7d is not None else None,
        }
        if term_row:
            data.update(
                {
                    "method": term_row["method"],
                    "leftExpiry": term_row["left_expiry_yyyymmdd"],
                    "rightExpiry": term_row["right_expiry_yyyymmdd"],
                }
            )
        for key, days in ATM_CHANGE_OFFSETS.items():
            past_row = _atm_term_metric_near(conn, tenor, latest_ts_ms - days * MS_PER_DAY)
            past_value = _nullable_num(past_row.get("atm_iv")) if past_row else None
            data[key] = atm_iv - past_value if atm_iv is not None and past_value is not None else None
        rows.append(data)
    return rows


def _atm_iv_table_from_expiry_metrics(
    conn,
    latest_ts_ms: int,
    expiry_metrics: list[dict],
    global_metrics: dict | None,
) -> list[dict]:
    history_by_offset = {
        key: _expiry_metrics_near(conn, latest_ts_ms - days * MS_PER_DAY)
        for key, days in ATM_CHANGE_OFFSETS.items()
    }
    rv_7d = _nullable_num((global_metrics or {}).get("rv_7d"))
    rows = []
    for tenor, target_dte in TENORS:
        atm_iv = _interpolate_expiry_field(expiry_metrics, target_dte, "atm_iv")
        data = {
            "tenor": tenor,
            "atmIv": atm_iv,
            "chg1d": None,
            "chg2d": None,
            "chg1w": None,
            "chg2w": None,
            "chg1m": None,
            "vrp1w": atm_iv - rv_7d if atm_iv is not None and rv_7d is not None else None,
        }
        for key, history_rows in history_by_offset.items():
            past_value = _interpolate_expiry_field(history_rows, target_dte, "atm_iv")
            data[key] = atm_iv - past_value if atm_iv is not None and past_value is not None else None
        rows.append(data)
    return rows


def _atm_term_metrics_at(conn, ts_ms: int) -> list[dict]:
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT
              ts_ms,
              tenor,
              target_dte_days,
              atm_iv,
              method,
              left_expiry_yyyymmdd,
              left_dte_days,
              left_atm_iv,
              right_expiry_yyyymmdd,
              right_dte_days,
              right_atm_iv
            FROM derived_atm_term_metrics
            WHERE ts_ms = ?
            ORDER BY CASE tenor
              WHEN '1D' THEN 1
              WHEN '1W' THEN 2
              WHEN '1M' THEN 3
              WHEN '3M' THEN 4
              WHEN '6M' THEN 5
              ELSE 99
            END
            """,
            (ts_ms,),
        )
    )


def _atm_term_metric_near(
    conn,
    tenor: str,
    target_ts_ms: int,
    *,
    tolerance_ms: int = CHANGE_LOOKUP_TOLERANCE_MS,
) -> dict | None:
    rows = _rows_as_dicts(
        conn.execute(
            """
            SELECT ts_ms, tenor, atm_iv
            FROM derived_atm_term_metrics
            WHERE tenor = ?
              AND ts_ms >= ?
              AND ts_ms <= ?
            ORDER BY abs(ts_ms - ?) ASC, ts_ms DESC
            LIMIT 1
            """,
            (tenor, target_ts_ms - tolerance_ms, target_ts_ms + tolerance_ms, target_ts_ms),
        )
    )
    return rows[0] if rows else None


def _skew_25d_table(conn, latest_ts_ms: int, expiry_metrics: list[dict]) -> list[dict]:
    history_by_offset = {
        key: _expiry_metrics_around(conn, latest_ts_ms - days * MS_PER_DAY)
        for key, days in ATM_CHANGE_OFFSETS.items()
    }
    rows = []
    for tenor, target_dte in TENORS:
        current = _interpolate_expiry_field_detail(expiry_metrics, target_dte, "skew_25d")
        skew_25d = current["value"]
        data = {
            "tenor": tenor,
            "skew25d": skew_25d,
            "chg1d": None,
            "chg2d": None,
            "chg1w": None,
            "chg2w": None,
            "chg1m": None,
            "method": current["method"],
            "leftExpiry": current["leftExpiry"],
            "rightExpiry": current["rightExpiry"],
        }
        for key, history_rows in history_by_offset.items():
            past_value = _interpolate_expiry_field_detail(
                history_rows,
                target_dte,
                "skew_25d",
            )["value"]
            data[key] = (
                skew_25d - past_value
                if skew_25d is not None and past_value is not None
                else None
            )
        rows.append(data)
    return rows


def _expiry_metrics_around(
    conn,
    target_ts_ms: int,
    *,
    tolerance_ms: int = CHANGE_LOOKUP_TOLERANCE_MS,
) -> list[dict]:
    row = conn.execute(
        """
        SELECT ts_ms
        FROM (
          SELECT DISTINCT ts_ms
          FROM derived_expiry_metrics
          WHERE ts_ms >= ?
            AND ts_ms <= ?
        )
        ORDER BY abs(ts_ms - ?) ASC, ts_ms DESC
        LIMIT 1
        """,
        (target_ts_ms - tolerance_ms, target_ts_ms + tolerance_ms, target_ts_ms),
    ).fetchone()
    return _expiry_metrics_at(conn, int(row[0])) if row else []


def _expiry_metrics_near(conn, target_ts_ms: int, *, tolerance_ms: int = 6 * 60 * 60 * 1000) -> list[dict]:
    row = conn.execute(
        """
        SELECT max(ts_ms)
        FROM derived_expiry_metrics
        WHERE ts_ms <= ?
        """,
        (target_ts_ms,),
    ).fetchone()
    if not row or row[0] is None:
        return []
    ts_ms = int(row[0])
    if target_ts_ms - ts_ms > tolerance_ms:
        return []
    return _expiry_metrics_at(conn, ts_ms)


def _vrp_history(
    global_rows: list[dict],
    price_rows: list[dict],
    *,
    max_history_points: int,
) -> list[dict]:
    sampled_rows = _sample_rows(global_rows, max_history_points)
    vol_lookup = _RealizedVolLookup(price_rows)
    points = []
    for row in sampled_rows:
        ts_ms = int(row["ts_ms"])
        for period in VRP_PERIODS:
            rv = _rv_for_period(row, period, ts_ms, vol_lookup)
            atm_iv = _atm_for_period(row, period)
            points.append(
                {
                    "tsMs": ts_ms,
                    "period": period,
                    "rv": rv,
                    "atmIv": atm_iv,
                    "vrp": atm_iv - rv if atm_iv is not None and rv is not None else None,
                }
            )
    return points


def _rv_for_period(row: dict, period: str, ts_ms: int, lookup: "_RealizedVolLookup") -> float | None:
    if period == "1D":
        return _nullable_num(row.get("rv_1d")) or lookup.value_at(ts_ms, 1)
    if period == "7D":
        return _nullable_num(row.get("rv_7d")) or lookup.value_at(ts_ms, 7)
    if period == "30D":
        return _nullable_num(row.get("rv_30d")) or lookup.value_at(ts_ms, 30)
    return lookup.value_at(ts_ms, 3)


def _atm_for_period(row: dict, period: str) -> float | None:
    if period == "30D":
        return _nullable_num(row.get("atm_iv_30d"))
    return _nullable_num(row.get("atm_iv_7d"))


class _RealizedVolLookup:
    def __init__(self, rows: list[dict]):
        valid = [
            (int(row["ts_ms"]), float(row["price"]))
            for row in rows
            if row.get("ts_ms") is not None and row.get("price") is not None and float(row["price"]) > 0
        ]
        valid.sort(key=lambda item: item[0])
        self.ts_values = [item[0] for item in valid]
        self.prices = [item[1] for item in valid]
        squared_returns = [0.0]
        for prev, curr in zip(self.prices, self.prices[1:]):
            squared_returns.append(math.log(curr / prev) ** 2 if prev > 0 and curr > 0 else 0.0)
        self.prefix = [0.0]
        for value in squared_returns:
            self.prefix.append(self.prefix[-1] + value)

    def value_at(self, ts_ms: int, window_days: int) -> float | None:
        if len(self.ts_values) < 2:
            return None
        start_ts_ms = ts_ms - window_days * MS_PER_DAY
        left = bisect_left(self.ts_values, start_ts_ms)
        right = bisect_right(self.ts_values, ts_ms) - 1
        if right <= left:
            return None
        elapsed_ms = self.ts_values[right] - self.ts_values[left]
        if elapsed_ms <= 0:
            return None
        sum_squared_returns = self.prefix[right + 1] - self.prefix[left + 1]
        elapsed_years = elapsed_ms / (365 * MS_PER_DAY)
        return math.sqrt(sum_squared_returns / elapsed_years)


def _default_expiry(metrics: list[dict]) -> str | None:
    if not metrics:
        return None
    return max(metrics, key=lambda row: float(row.get("total_oi") or 0)).get("expiry_yyyymmdd")


def _interpolate_expiry_field(metrics: list[dict], target_dte_days: float, field: str) -> float | None:
    return _interpolate_expiry_field_detail(metrics, target_dte_days, field)["value"]


def _interpolate_expiry_field_detail(
    metrics: list[dict],
    target_dte_days: float,
    field: str,
) -> dict:
    points = _expiry_field_points(metrics, field)
    if not points:
        return {
            "value": None,
            "method": "unavailable",
            "leftExpiry": None,
            "rightExpiry": None,
        }
    if target_dte_days <= points[0]["dte"]:
        return _term_interpolation_result(points[0], points[0], points[0]["value"], "nearest_front_expiry")
    if target_dte_days >= points[-1]["dte"]:
        return _term_interpolation_result(points[-1], points[-1], points[-1]["value"], "nearest_back_expiry")
    for left, right in zip(points, points[1:]):
        if left["dte"] <= target_dte_days <= right["dte"]:
            span = right["dte"] - left["dte"]
            if span == 0:
                value = left["value"]
            else:
                weight = (target_dte_days - left["dte"]) / span
                value = left["value"] + weight * (right["value"] - left["value"])
            return _term_interpolation_result(left, right, value, "linear_interpolation")
    return _term_interpolation_result(points[-1], points[-1], points[-1]["value"], "nearest_back_expiry")


def _expiry_field_points(metrics: list[dict], field: str) -> list[dict]:
    return sorted(
        (
            {
                "expiry": row["expiry_yyyymmdd"],
                "dte": float(row["dte_days"]),
                "value": float(row[field]),
            }
            for row in metrics
            if row.get("dte_days") is not None and row.get(field) is not None
        ),
        key=lambda point: point["dte"],
    )


def _term_interpolation_result(left: dict, right: dict, value: float | None, method: str) -> dict:
    return {
        "value": value,
        "method": method,
        "leftExpiry": left["expiry"],
        "rightExpiry": right["expiry"],
    }


def _sample_rows(rows: list[dict], max_points: int) -> list[dict]:
    if len(rows) <= max_points:
        return rows
    last_index = len(rows) - 1
    indexes = sorted({round(index * last_index / (max_points - 1)) for index in range(max_points)})
    return [rows[index] for index in indexes]


def _rows_as_dicts(cursor) -> list[dict]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _format_timestamp(ts_ms: int) -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S UTC+08")


def _nullable_num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)
