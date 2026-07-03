from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from threading import Lock
from typing import Any, Awaitable, Callable

from hype_options.dashboard_data import _vrp_history
from hype_options.dashboard_read_model import (
    RuntimeDashboardSnapshot,
    dashboard_panel_payloads,
    vol_regime_from_terms,
)
from hype_options.db import Repository, apply_options_history_schema, connect_database
from hype_options.metrics import compute_global_metrics

try:
    from starlette.websockets import WebSocketDisconnect
except ModuleNotFoundError:
    WebSocketDisconnect = RuntimeError

WebSocket = Any


MS_PER_DAY = 86_400_000
TENORS = [
    ("1D", 1),
    ("1W", 7),
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
]
SKEW_FLY_TENORS = TENORS + [("1Y", 365)]
CHANGE_OFFSETS = {
    "chg1d": 1,
    "chg2d": 2,
    "chg1w": 7,
    "chg2w": 14,
    "chg1m": 30,
}
CHANGE_LOOKUP_TOLERANCE_MS = 20 * 60 * 1000


@dataclass
class ClientState:
    websocket: WebSocket
    panels: dict[str, dict[str, Any]] = field(default_factory=dict)


class DashboardConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[int, ClientState] = {}

    @property
    def has_clients(self) -> bool:
        return bool(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients[id(websocket)] = ClientState(websocket=websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.pop(id(websocket), None)

    def subscribe(self, websocket: WebSocket, panel: str, params: dict[str, Any] | None = None) -> None:
        state = self._clients.get(id(websocket))
        if state is None:
            return
        state.panels[panel] = params or {}

    def subscribe_many(self, websocket: WebSocket, panels: list[str], params: dict[str, Any] | None = None) -> None:
        for panel in panels:
            self.subscribe(websocket, panel, params)

    async def receive_loop(self, websocket: WebSocket) -> None:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "subscribe":
                panels = message.get("panels") or ["summary"]
                params = {key: value for key, value in message.items() if key not in {"type", "panels"}}
                self.subscribe_many(websocket, [str(panel) for panel in panels], params)
                await websocket.send_json({"type": "subscribed", "panels": panels})
            elif message_type == "panel.subscribe":
                panel = str(message.get("panel") or "")
                params = message.get("params") or {}
                if panel:
                    self.subscribe(websocket, panel, params)
                    await websocket.send_json({"type": "panel.subscribed", "panel": panel, "params": params})

    async def broadcast_snapshot(
        self,
        *,
        snapshot_id: int,
        payload_builder: Callable[[dict[str, dict[str, Any]]], dict[str, Any]],
        message_type: str = "dashboard.update",
    ) -> None:
        dead: list[WebSocket] = []
        for state in list(self._clients.values()):
            panels = state.panels or {
                "snapshot": {},
                "summary": {},
                "expiries": {},
                "atmTerm": {},
                "skewFly": {},
                "oiByExpiry": {},
            }
            try:
                await state.websocket.send_json(
                    {
                        "type": message_type,
                        "snapshotId": snapshot_id,
                        "payload": payload_builder(panels),
                    }
                )
            except WebSocketDisconnect:
                dead.append(state.websocket)
            except RuntimeError:
                dead.append(state.websocket)
        for websocket in dead:
            self.disconnect(websocket)

    async def broadcast_panel_update(
        self,
        *,
        panel: str,
        snapshot_id: int,
        payload_builder: Callable[[dict[str, Any]], Any],
        message_type: str = "dashboard.update",
    ) -> None:
        dead: list[WebSocket] = []
        for state in list(self._clients.values()):
            if panel not in state.panels:
                continue
            params = state.panels.get(panel) or {}
            try:
                await state.websocket.send_json(
                    {
                        "type": message_type,
                        "snapshotId": snapshot_id,
                        "payload": {panel: payload_builder(params)},
                    }
                )
            except WebSocketDisconnect:
                dead.append(state.websocket)
            except RuntimeError:
                dead.append(state.websocket)
        for websocket in dead:
            self.disconnect(websocket)


@dataclass(frozen=True)
class LightweightHistoryWriteResult:
    price_snapshots: int
    expiry_metrics: int
    atm_term_metrics: int
    global_metrics: int


class OptionsRealtimeService:
    def __init__(self, settings) -> None:
        self.settings = settings
        self._snapshot: RuntimeDashboardSnapshot | None = None
        self._last_error: str | None = None
        self._lock = Lock()
        self._instrument_payload: dict[str, Any] | None = None
        self._instrument_refresh_ms = 0
        self._next_history_write_ms = 0

    @property
    def refresh_seconds(self) -> int:
        return self.settings.options_realtime_refresh_seconds

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def get_snapshot(self) -> RuntimeDashboardSnapshot | None:
        with self._lock:
            return self._snapshot

    def panel_payloads(self, panels: dict[str, dict[str, Any]]) -> dict[str, Any]:
        snapshot = self.get_snapshot()
        if snapshot is None:
            return {}
        return dashboard_panel_payloads(snapshot, panels)

    def refresh_once(self, *, force_history_write: bool = False) -> RuntimeDashboardSnapshot:
        try:
            result = self._collect_current_surface()
            now_ms = int(time.time() * 1000)
            should_write_history = force_history_write or now_ms >= self._next_history_write_ms
            conn = connect_database(
                self.settings.database_url,
                self.settings.database_auth_token,
            )
            try:
                apply_options_history_schema(conn)
                if should_write_history:
                    write_lightweight_history(conn, result)
                    self._next_history_write_ms = (
                        result.price_snapshots[0].ts_ms
                        + self.settings.options_history_write_seconds * 1000
                    )
                snapshot = build_realtime_dashboard_snapshot(
                    result,
                    conn,
                    lookback_days=self.settings.options_history_lookback_days,
                )
            finally:
                conn.close()
            with self._lock:
                self._snapshot = snapshot
                self._last_error = None
            return snapshot
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise

    async def refresh_loop(self, manager: DashboardConnectionManager | None = None) -> None:
        while True:
            try:
                snapshot = await asyncio.to_thread(self.refresh_once)
                if manager is not None and manager.has_clients:
                    await manager.broadcast_snapshot(
                        snapshot_id=snapshot.snapshot_id,
                        payload_builder=self._build_broadcast_payload,
                        message_type="options.update",
                    )
            except Exception:
                pass
            await asyncio.sleep(max(1, self.refresh_seconds))

    def _build_broadcast_payload(self, panels: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return self.panel_payloads(panels)

    def _collect_current_surface(self):
        from hype_options.collector import collect_from_payloads
        from hype_options.derive_client import DeriveClient
        from hype_options.normalizer import normalize_instruments

        snapshot_ms = int(time.time() * 1000)
        client = DeriveClient(
            base_url=self.settings.derive_base_url,
            currency=self.settings.derive_currency,
        )
        if (
            self._instrument_payload is None
            or snapshot_ms - self._instrument_refresh_ms
            >= self.settings.derive_instrument_refresh_seconds * 1000
        ):
            self._instrument_payload = client.get_instruments()
            self._instrument_refresh_ms = snapshot_ms
        instruments = normalize_instruments(self._instrument_payload, seen_ms=snapshot_ms)
        expiries = sorted(
            {item.expiry_yyyymmdd for item in instruments if item.is_active}
        )
        ticker_payloads = {expiry: client.get_tickers(expiry) for expiry in expiries}
        return collect_from_payloads(
            instruments_payload=self._instrument_payload,
            ticker_payloads_by_expiry=ticker_payloads,
            snapshot_ms=snapshot_ms,
            raw_payload_retention_days=self.settings.raw_payload_retention_days,
        )


def write_lightweight_history(conn, result) -> LightweightHistoryWriteResult:
    apply_options_history_schema(conn)
    repository = Repository(conn)
    global_metric = _global_metric_with_history(conn, result)
    repository.insert_price_snapshots(result.price_snapshots)
    repository.insert_expiry_metrics(result.expiry_metrics)
    repository.insert_atm_term_metrics(result.atm_term_metrics)
    if global_metric is not None:
        repository.insert_global_metrics([global_metric])
    return LightweightHistoryWriteResult(
        price_snapshots=len(result.price_snapshots),
        expiry_metrics=len(result.expiry_metrics),
        atm_term_metrics=len(result.atm_term_metrics),
        global_metrics=1 if global_metric is not None else 0,
    )


def build_realtime_dashboard_snapshot(
    result,
    conn,
    *,
    selected_expiry: str | None = None,
    lookback_days: int = 365,
) -> RuntimeDashboardSnapshot:
    latest_ts_ms = _result_ts_ms(result)
    generated_at_ms = int(time.time() * 1000)
    expiry_metrics = list(result.expiry_metrics)
    atm_terms = list(result.atm_term_metrics)
    current_global_metric = _global_metric_with_history(conn, result)
    current_price = _spot_price(result)

    history_global_rows = _history_global_rows(conn, latest_ts_ms, lookback_days)
    if current_global_metric is not None:
        history_global_rows = _replace_history_row(
            history_global_rows,
            _global_metric_dict(current_global_metric),
            ("ts_ms",),
        )
    history_price_rows = _history_price_rows(conn, latest_ts_ms, lookback_days + 31)
    for price_snapshot in result.price_snapshots:
        history_price_rows = _replace_history_row(
            history_price_rows,
            {
                "ts_ms": price_snapshot.ts_ms,
                "price": price_snapshot.price,
            },
            ("ts_ms",),
        )
    history_term_rows = _history_atm_term_rows(conn, latest_ts_ms, lookback_days)
    history_expiry_rows = _history_expiry_rows(conn, latest_ts_ms, lookback_days)

    default_expiry = selected_expiry or _default_expiry(expiry_metrics)
    iv_smile_by_expiry = _iv_smile_by_expiry(result.ticker_rows)
    oi_by_strike = _oi_by_strike(result.ticker_rows)
    vol_regime = vol_regime_from_terms(
        current_terms=[_atm_term_dict(row) for row in atm_terms],
        history_rows=history_term_rows,
        tenor="1M",
        lookback_days=lookback_days,
        latest_ts_ms=latest_ts_ms,
    )
    atm_term = _atm_iv_table(
        current_terms=atm_terms,
        global_metric=current_global_metric,
        history_rows=history_term_rows,
        latest_ts_ms=latest_ts_ms,
    )
    skew_fly = _skew_25d_table(
        expiry_metrics=expiry_metrics,
        history_rows=history_expiry_rows,
        latest_ts_ms=latest_ts_ms,
    )
    summary = _summary_from_current(current_global_metric, atm_term, vol_regime)
    bootstrap = {
        "snapshot": {
            "latestTsMs": latest_ts_ms,
            "snapshotLabel": _format_timestamp(latest_ts_ms),
            "generatedAt": _format_timestamp(generated_at_ms),
            "source": "derive_realtime_cache",
        },
        "summary": summary,
        "selectedExpiry": default_expiry,
        "expiries": [_serialize_expiry_metric(row) for row in expiry_metrics],
        "atmTerm": atm_term,
        "skewFly": skew_fly,
        "ivSmile": iv_smile_by_expiry.get(default_expiry or "", []),
        "ivSmileByExpiry": iv_smile_by_expiry,
        "gexByStrike": _gex_by_strike(result.gex_by_strike),
        "gexByExpiry": _gex_by_expiry(result.gex_by_strike, expiry_metrics),
        "oiByStrike": oi_by_strike,
        "oiByExpiry": _oi_by_expiry(expiry_metrics),
        "vrpHistory": _vrp_history(
            sorted(history_global_rows, key=lambda row: row["ts_ms"]),
            sorted(history_price_rows, key=lambda row: row["ts_ms"]),
            max_history_points=720,
        ),
        "volRegime": vol_regime,
    }
    if summary.get("spotPrice") is None and current_price is not None:
        summary["spotPrice"] = current_price
    return RuntimeDashboardSnapshot(
        snapshot_id=latest_ts_ms,
        bootstrap=bootstrap,
        iv_smile_by_expiry=iv_smile_by_expiry,
        oi_by_strike=oi_by_strike,
        vol_regime_history=history_term_rows,
        current_atm_terms=[_atm_term_dict(row) for row in atm_terms],
        lookback_days=lookback_days,
    )


def _global_metric_with_history(conn, result):
    spot_price = _spot_price(result)
    if spot_price is None:
        return result.global_metrics[0] if result.global_metrics else None
    ts_ms = _result_ts_ms(result)
    price_points = _price_points_since(conn, ts_ms - 31 * MS_PER_DAY)
    if not any(point["ts_ms"] == ts_ms for point in price_points):
        price_points.append({"ts_ms": ts_ms, "price": spot_price})
    return compute_global_metrics(
        expiry_metrics=result.expiry_metrics,
        price_points=price_points,
        ts_ms=ts_ms,
        spot_price=spot_price,
    )


def _result_ts_ms(result) -> int:
    if result.price_snapshots:
        return int(result.price_snapshots[0].ts_ms)
    if result.expiry_metrics:
        return int(result.expiry_metrics[0].ts_ms)
    if result.ticker_rows:
        return int(result.ticker_rows[0].ts_ms)
    return int(time.time() * 1000)


def _spot_price(result) -> float | None:
    if result.price_snapshots:
        return float(result.price_snapshots[0].price)
    for row in result.ticker_rows:
        if row.index_price is not None:
            return float(row.index_price)
    return None


def _summary_from_current(global_metric, atm_term: list[dict[str, Any]], vol_regime: dict[str, Any]) -> dict[str, Any]:
    atm_by_tenor = {row.get("tenor"): row.get("atmIv") for row in atm_term}
    return {
        "spotPrice": _nullable_attr(global_metric, "spot_price"),
        "totalOptionOi": _num_attr(global_metric, "total_option_oi"),
        "totalOptionVolume": _num_attr(global_metric, "total_option_volume"),
        "putCallVolumeRatio": _nullable_attr(global_metric, "put_call_volume_ratio"),
        "netGex": _num_attr(global_metric, "net_gex"),
        "absGex": _num_attr(global_metric, "abs_gex"),
        "vrp7d": _nullable_attr(global_metric, "vrp_7d"),
        "vrp30d": _nullable_attr(global_metric, "vrp_30d"),
        "atmIv": {tenor: atm_by_tenor.get(tenor) for tenor, _ in TENORS},
        "ivRank": vol_regime.get("ivRank"),
        "ivPercentile": vol_regime.get("ivPercentile"),
        "volRegimeTenor": vol_regime.get("tenor"),
        "volRegimeLookbackDays": vol_regime.get("lookbackDays"),
    }


def _serialize_expiry_metric(row) -> dict[str, Any]:
    return {
        "expiry": row.expiry_yyyymmdd,
        "dte": _nullable_num(row.dte_days),
        "atmIv": _nullable_num(row.atm_iv),
        "atmStrike": _nullable_num(row.atm_strike),
        "call25dIv": _nullable_num(row.call_25d_iv),
        "put25dIv": _nullable_num(row.put_25d_iv),
        "skew25d": _nullable_num(row.skew_25d),
        "fly25d": _nullable_num(row.fly_25d),
        "totalOi": _num(row.total_oi),
        "callOi": _num(row.call_oi),
        "putOi": _num(row.put_oi),
        "totalVolume": _num(row.total_volume),
        "callVolume": _num(row.call_volume),
        "putVolume": _num(row.put_volume),
        "maxPain": _nullable_num(row.max_pain_price),
        "netGex": _num(row.net_gex),
        "absGex": _num(row.abs_gex),
        "tradablePoints": int(row.tradable_point_count or 0),
        "modelPoints": int(row.model_point_count or 0),
    }


def _atm_iv_table(
    *,
    current_terms,
    global_metric,
    history_rows: list[dict[str, Any]],
    latest_ts_ms: int,
) -> list[dict[str, Any]]:
    current_by_tenor = {row.tenor: row for row in current_terms}
    rv_7d = _nullable_attr(global_metric, "rv_7d")
    rows = []
    for tenor, _target_dte in TENORS:
        term = current_by_tenor.get(tenor)
        atm_iv = _nullable_num(term.atm_iv) if term else None
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
        if term:
            data.update(
                {
                    "method": term.method,
                    "leftExpiry": term.left_expiry_yyyymmdd,
                    "rightExpiry": term.right_expiry_yyyymmdd,
                }
            )
        for key, days in CHANGE_OFFSETS.items():
            past = _term_history_near(
                history_rows,
                tenor,
                latest_ts_ms - days * MS_PER_DAY,
            )
            past_value = _nullable_num(past.get("atm_iv")) if past else None
            data[key] = atm_iv - past_value if atm_iv is not None and past_value is not None else None
        rows.append(data)
    return rows


def _skew_25d_table(
    *,
    expiry_metrics,
    history_rows: list[dict[str, Any]],
    latest_ts_ms: int,
) -> list[dict[str, Any]]:
    rows = []
    for tenor, target_dte in SKEW_FLY_TENORS:
        skew = _interpolate_expiry_field_detail(expiry_metrics, target_dte, "skew_25d")
        fly = _interpolate_expiry_field_detail(expiry_metrics, target_dte, "fly_25d")
        data = {
            "tenor": tenor,
            "skew25d": skew["value"],
            "fly25d": fly["value"],
            "chg1d": None,
            "chg2d": None,
            "chg1w": None,
            "chg2w": None,
            "chg1m": None,
            "flyChg1d": None,
            "flyChg2d": None,
            "flyChg1w": None,
            "flyChg2w": None,
            "flyChg1m": None,
            "method": skew["method"],
            "leftExpiry": skew["leftExpiry"],
            "rightExpiry": skew["rightExpiry"],
            "flyMethod": fly["method"],
            "flyLeftExpiry": fly["leftExpiry"],
            "flyRightExpiry": fly["rightExpiry"],
        }
        for key, days in CHANGE_OFFSETS.items():
            past_rows = _expiry_history_near(
                history_rows,
                latest_ts_ms - days * MS_PER_DAY,
            )
            past_value = _interpolate_expiry_field_detail(
                past_rows,
                target_dte,
                "skew_25d",
            )["value"]
            past_fly_value = _interpolate_expiry_field_detail(
                past_rows,
                target_dte,
                "fly_25d",
            )["value"]
            data[key] = (
                skew["value"] - past_value
                if skew["value"] is not None and past_value is not None
                else None
            )
            data[f"fly{key[0].upper()}{key[1:]}"] = (
                fly["value"] - past_fly_value
                if fly["value"] is not None and past_fly_value is not None
                else None
            )
        rows.append(data)
    return rows


def _iv_smile_by_expiry(ticker_rows) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[float, dict[str, Any]]] = {}
    for row in ticker_rows:
        if row.surface_quality == "invalid" or row.mark_iv is None:
            continue
        by_strike = grouped.setdefault(row.expiry_yyyymmdd, {})
        point = by_strike.setdefault(
            float(row.strike),
            {
                "strike": float(row.strike),
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
        if row.option_type == "C":
            point["callIv"] = _nullable_num(row.mark_iv)
            point["callDelta"] = _nullable_num(row.delta)
            point["callGamma"] = _nullable_num(row.gamma)
            point["callVega"] = _nullable_num(row.vega)
            point["callTheta"] = _nullable_num(row.theta)
            point["callRho"] = _nullable_num(row.rho)
            point["callPremium"] = _nullable_num(row.mark_price if row.mark_price is not None else row.mid_price)
            point["callOi"] = _num(row.open_interest)
        elif row.option_type == "P":
            point["putIv"] = _nullable_num(row.mark_iv)
            point["putDelta"] = _nullable_num(row.delta)
            point["putGamma"] = _nullable_num(row.gamma)
            point["putVega"] = _nullable_num(row.vega)
            point["putTheta"] = _nullable_num(row.theta)
            point["putRho"] = _nullable_num(row.rho)
            point["putPremium"] = _nullable_num(row.mark_price if row.mark_price is not None else row.mid_price)
            point["putOi"] = _num(row.open_interest)
    return {
        expiry: [by_strike[strike] for strike in sorted(by_strike)]
        for expiry, by_strike in grouped.items()
    }


def _oi_by_strike(ticker_rows) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float], dict[str, Any]] = {}
    for row in ticker_rows:
        key = (row.expiry_yyyymmdd, float(row.strike))
        point = grouped.setdefault(
            key,
            {
                "expiry": row.expiry_yyyymmdd,
                "strike": float(row.strike),
                "callOi": 0.0,
                "putOi": 0.0,
                "totalOi": 0.0,
            },
        )
        if row.option_type == "C":
            point["callOi"] += _num(row.open_interest)
        elif row.option_type == "P":
            point["putOi"] += _num(row.open_interest)
        point["totalOi"] = point["callOi"] + point["putOi"]
    return [grouped[key] for key in sorted(grouped)]


def _gex_by_strike(rows) -> list[dict[str, Any]]:
    grouped: dict[float, dict[str, Any]] = {}
    for row in rows:
        point = grouped.setdefault(
            float(row.strike),
            {"strike": float(row.strike), "callGex": 0.0, "putGex": 0.0, "netGex": 0.0, "absGex": 0.0},
        )
        point["callGex"] += _num(row.call_gex)
        point["putGex"] += _num(row.put_gex)
        point["netGex"] += _num(row.net_gex)
        point["absGex"] += _num(row.abs_gex)
    return [grouped[strike] for strike in sorted(grouped)]


def _gex_by_expiry(rows, expiry_metrics) -> list[dict[str, Any]]:
    expiry_lookup = {
        metric.expiry_ts_ms: metric.expiry_yyyymmdd
        for metric in expiry_metrics
    }
    return [
        {
            "expiry": expiry_lookup.get(row.expiry_ts_ms),
            "strike": _num(row.strike),
            "callGex": _num(row.call_gex),
            "putGex": _num(row.put_gex),
            "netGex": _num(row.net_gex),
            "absGex": _num(row.abs_gex),
        }
        for row in sorted(rows, key=lambda item: (item.expiry_ts_ms, item.strike))
    ]


def _oi_by_expiry(expiry_metrics) -> list[dict[str, Any]]:
    return [
        {
            "expiry": row.expiry_yyyymmdd,
            "totalOi": _num(row.total_oi),
            "callOi": _num(row.call_oi),
            "putOi": _num(row.put_oi),
            "totalVolume": _num(row.total_volume),
            "callVolume": _num(row.call_volume),
            "putVolume": _num(row.put_volume),
        }
        for row in sorted(expiry_metrics, key=lambda item: item.expiry_ts_ms)
    ]


def _price_points_since(conn, start_ts_ms: int) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT ts_ms, price
            FROM hype_price_snapshots
            WHERE ts_ms >= ?
            ORDER BY ts_ms
            """,
            (start_ts_ms,),
        )
    )


def _history_global_rows(conn, latest_ts_ms: int, lookback_days: int) -> list[dict[str, Any]]:
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
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


def _history_price_rows(conn, latest_ts_ms: int, lookback_days: int) -> list[dict[str, Any]]:
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
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


def _history_atm_term_rows(conn, latest_ts_ms: int, lookback_days: int) -> list[dict[str, Any]]:
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
    return _rows_as_dicts(
        conn.execute(
            """
            SELECT ts_ms, tenor, target_dte_days, atm_iv, method,
                   left_expiry_yyyymmdd, left_dte_days, left_atm_iv,
                   right_expiry_yyyymmdd, right_dte_days, right_atm_iv
            FROM derived_atm_term_metrics
            WHERE ts_ms >= ? AND ts_ms <= ?
            ORDER BY ts_ms, tenor
            """,
            (start_ts_ms, latest_ts_ms),
        )
    )


def _history_expiry_rows(conn, latest_ts_ms: int, lookback_days: int) -> list[dict[str, Any]]:
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
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
              fly_25d
            FROM derived_expiry_metrics
            WHERE ts_ms >= ? AND ts_ms <= ?
            ORDER BY ts_ms, expiry_ts_ms
            """,
            (start_ts_ms, latest_ts_ms),
        )
    )


def _replace_history_row(
    rows: list[dict[str, Any]],
    replacement: dict[str, Any],
    key_columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    replacement_key = tuple(replacement.get(column) for column in key_columns)
    next_rows = [
        row for row in rows
        if tuple(row.get(column) for column in key_columns) != replacement_key
    ]
    next_rows.append(replacement)
    return next_rows


def _term_history_near(
    rows: list[dict[str, Any]],
    tenor: str,
    target_ts_ms: int,
) -> dict[str, Any] | None:
    candidates = [
        row for row in rows
        if row.get("tenor") == tenor
        and abs(int(row["ts_ms"]) - target_ts_ms) <= CHANGE_LOOKUP_TOLERANCE_MS
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda row: (abs(int(row["ts_ms"]) - target_ts_ms), -int(row["ts_ms"])))


def _expiry_history_near(
    rows: list[dict[str, Any]],
    target_ts_ms: int,
    *,
    tolerance_ms: int = 6 * 60 * 60 * 1000,
) -> list[dict[str, Any]]:
    timestamps = sorted({int(row["ts_ms"]) for row in rows if int(row["ts_ms"]) <= target_ts_ms})
    if not timestamps:
        return []
    ts_ms = timestamps[-1]
    if target_ts_ms - ts_ms > tolerance_ms:
        return []
    return [row for row in rows if int(row["ts_ms"]) == ts_ms]


def _interpolate_expiry_field_detail(metrics, target_dte_days: float, field: str) -> dict[str, Any]:
    points = _expiry_field_points(metrics, field)
    if not points:
        return {"value": None, "method": "unavailable", "leftExpiry": None, "rightExpiry": None}
    if target_dte_days <= points[0]["dte"]:
        return _term_interpolation_result(points[0], points[0], points[0]["value"], "nearest_front_expiry")
    if target_dte_days >= points[-1]["dte"]:
        return _term_interpolation_result(points[-1], points[-1], points[-1]["value"], "nearest_back_expiry")
    for left, right in zip(points, points[1:]):
        if left["dte"] <= target_dte_days <= right["dte"]:
            span = right["dte"] - left["dte"]
            value = left["value"] if span == 0 else left["value"] + (target_dte_days - left["dte"]) / span * (right["value"] - left["value"])
            return _term_interpolation_result(left, right, value, "linear_interpolation")
    return _term_interpolation_result(points[-1], points[-1], points[-1]["value"], "nearest_back_expiry")


def _expiry_field_points(metrics, field: str) -> list[dict[str, Any]]:
    points = []
    for row in metrics:
        dte = _field_value(row, "dte_days")
        value = _field_value(row, field)
        if dte is None or value is None:
            continue
        points.append(
            {
                "expiry": _field_value(row, "expiry_yyyymmdd"),
                "dte": float(dte),
                "value": float(value),
            }
        )
    return sorted(points, key=lambda point: point["dte"])


def _term_interpolation_result(left: dict[str, Any], right: dict[str, Any], value: float | None, method: str) -> dict[str, Any]:
    return {
        "value": value,
        "method": method,
        "leftExpiry": left["expiry"],
        "rightExpiry": right["expiry"],
    }


def _default_expiry(metrics) -> str | None:
    if not metrics:
        return None
    return max(metrics, key=lambda row: float(row.total_oi or 0)).expiry_yyyymmdd


def _global_metric_dict(row) -> dict[str, Any]:
    return {
        "ts_ms": row.ts_ms,
        "rv_1d": row.rv_1d,
        "rv_7d": row.rv_7d,
        "rv_30d": row.rv_30d,
        "atm_iv_7d": row.atm_iv_7d,
        "atm_iv_30d": row.atm_iv_30d,
    }


def _atm_term_dict(row) -> dict[str, Any]:
    return {
        "ts_ms": row.ts_ms,
        "tenor": row.tenor,
        "target_dte_days": row.target_dte_days,
        "atm_iv": row.atm_iv,
        "method": row.method,
        "left_expiry_yyyymmdd": row.left_expiry_yyyymmdd,
        "left_dte_days": row.left_dte_days,
        "left_atm_iv": row.left_atm_iv,
        "right_expiry_yyyymmdd": row.right_expiry_yyyymmdd,
        "right_dte_days": row.right_dte_days,
        "right_atm_iv": row.right_atm_iv,
    }


def _field_value(row, field: str) -> Any:
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field)


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _format_timestamp(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S UTC+08")


def _nullable_attr(row, attr: str) -> float | None:
    if row is None:
        return None
    return _nullable_num(getattr(row, attr))


def _num_attr(row, attr: str) -> float:
    if row is None:
        return 0.0
    return _num(getattr(row, attr))


def _nullable_num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)
