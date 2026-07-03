from __future__ import annotations

import asyncio
import os
import time
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from hype_options.config import Settings
from hype_options.dashboard_queries import (
    latest_order_flow_ts,
)
from hype_options.db import connect_database
from hype_options.instruments import (
    format_option_instrument,
    option_type_code,
)
from hype_options.market_data import (
    complete_ticker_map_for_positions,
    option_choices,
    ticker_map_from_latest_database_snapshot,
    ticker_map_from_payload as market_ticker_map_from_payload,
    ticker_map_from_realtime_snapshot,
)
from hype_options.order_flow import get_order_flow_events
from hype_options.portfolio_risk import (
    evaluate_portfolio_positions,
    evaluate_strategy_legs,
    validate_single_asset_positions,
)
from hype_options.realtime import DashboardConnectionManager, OptionsRealtimeService
from hype_options.strategy_templates import generate_strategy_legs
from hype_options.wallet_lookup import (
    WalletLookupClient,
    WalletLookupError,
    is_valid_wallet_address,
)

app = FastAPI(title="HYPE Options Dashboard API")
manager = DashboardConnectionManager()
_options_task: asyncio.Task | None = None
_order_flow_task: asyncio.Task | None = None
_options_service: OptionsRealtimeService | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("DASHBOARD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def _options_connection():
    settings = Settings.from_env()
    conn = connect_database(settings.database_url, settings.database_auth_token)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _order_flow_connection():
    settings = Settings.from_env()
    conn = connect_database(
        settings.order_flow_database_url,
        settings.order_flow_database_auth_token,
    )
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/options/dashboard/bootstrap")
def dashboard_bootstrap(expiry: str | None = None, lookbackDays: int = 365) -> dict[str, Any]:
    return _current_options_snapshot().bootstrap_payload(
        selected_expiry=expiry,
        lookback_days=lookbackDays,
    )


@app.get("/api/options/iv-smile")
def iv_smile(expiry: str) -> list[dict[str, Any]]:
    return _current_options_snapshot().panel_payload("ivSmile", {"expiry": expiry})


@app.get("/api/options/gex-by-strike")
def gex_by_strike() -> list[dict[str, Any]]:
    return _current_options_snapshot().panel_payload("gexByStrike")


@app.get("/api/options/gex-by-expiry")
def gex_by_expiry() -> list[dict[str, Any]]:
    return _current_options_snapshot().panel_payload("gexByExpiry")


@app.get("/api/options/oi-by-strike")
def oi_by_strike() -> list[dict[str, Any]]:
    return _current_options_snapshot().panel_payload("oiByStrike")


@app.get("/api/options/oi-by-expiry")
def oi_by_expiry() -> list[dict[str, Any]]:
    return _current_options_snapshot().panel_payload("oiByExpiry")


@app.get("/api/options/vol-regime")
def vol_regime(tenor: str = "1M", lookbackDays: int = 365) -> dict[str, Any]:
    return _current_options_snapshot().panel_payload(
        "volRegime",
        {"tenor": tenor, "lookbackDays": lookbackDays},
    )


@app.get("/api/order-flow/events")
def order_flow_events(
    executionType: str | None = None,
    legStructure: str | None = None,
    optionMix: str | None = None,
    side: str | None = None,
    orderType: str | None = None,
    timeInForce: str | None = None,
    minAmount: float | None = None,
    minPremiumUsd: float | None = None,
    wallet: str | None = None,
    subaccountId: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with _order_flow_connection() as conn:
        return get_order_flow_events(
            conn,
            execution_type=executionType,
            leg_structure=legStructure,
            option_mix=optionMix,
            side=side,
            order_type=orderType,
            time_in_force=timeInForce,
            min_amount=minAmount,
            min_premium_usd=minPremiumUsd,
            wallet=wallet,
            subaccount_id=subaccountId,
            limit=limit,
        )


@app.get("/api/greek-strategy/wallet")
def greek_strategy_wallet(address: str) -> dict[str, Any]:
    if not is_valid_wallet_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    try:
        return WalletLookupClient(base_url=_derive_app_base_url()).fetch_wallet(address)
    except WalletLookupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/greek-strategy/portfolio-greeks")
def greek_strategy_portfolio_greeks(payload: dict[str, Any]) -> dict[str, Any]:
    positions = _required_list(payload, "positions")
    metric = str(payload.get("metric") or "delta").lower()
    try:
        validate_single_asset_positions(positions)
        ticker_map = _ticker_map_for_positions(positions, _ticker_map_from_payload(payload))
        return evaluate_portfolio_positions(positions, ticker_map, metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/greek-strategy/options")
def greek_strategy_options() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {"options": option_choices(_current_ticker_map(), now_ms=now_ms)}


@app.post("/api/greek-strategy/simulate")
def greek_strategy_simulate(payload: dict[str, Any]) -> dict[str, Any]:
    legs = _simulation_legs(payload)
    ticker_map = _ticker_map_from_payload(payload)
    metric = str(payload.get("metric") or "delta").lower()
    try:
        return evaluate_strategy_legs(legs, ticker_map, metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/greek-strategy/strategy-preview")
def greek_strategy_strategy_preview(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        legs = generate_strategy_legs(
            str(payload.get("strategy") or ""),
            expiry=str(payload.get("expiry") or ""),
            strikes=_required_list(payload, "strikes"),
            quantity=float(payload.get("quantity") or 1),
            side=str(payload.get("side") or "buy"),
            custom_legs=payload.get("legs") if isinstance(payload.get("legs"), list) else None,
        )
        ticker_map = _ticker_map_from_payload(payload)
        metric = str(payload.get("metric") or "delta").lower()
        return evaluate_strategy_legs(legs, ticker_map, metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/options")
async def options_socket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await manager.receive_loop(websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def start_dashboard_polling() -> None:
    global _options_service, _options_task, _order_flow_task
    if _options_service is None:
        _options_service = OptionsRealtimeService(Settings.from_env())
    if _options_task is None:
        _options_task = asyncio.create_task(_options_service.refresh_loop(manager))
    if _order_flow_task is None:
        _order_flow_task = asyncio.create_task(broadcast_order_flow_updates())


@app.on_event("shutdown")
async def stop_dashboard_polling() -> None:
    global _options_task, _order_flow_task
    if _options_task is not None:
        _options_task.cancel()
        try:
            await _options_task
        except asyncio.CancelledError:
            pass
        _options_task = None
    if _order_flow_task is not None:
        _order_flow_task.cancel()
        try:
            await _order_flow_task
        except asyncio.CancelledError:
            pass
        _order_flow_task = None


async def broadcast_order_flow_updates() -> None:
    poll_seconds = float(os.getenv("ORDER_FLOW_WS_POLL_SECONDS", "5"))
    last_order_flow_id: int | None = None
    while True:
        await asyncio.sleep(poll_seconds)
        if not manager.has_clients:
            continue
        try:
            with _order_flow_connection() as order_flow_conn:
                order_flow_id = latest_order_flow_ts(order_flow_conn)
                if order_flow_id is None or order_flow_id == last_order_flow_id:
                    continue
                last_order_flow_id = order_flow_id
                await manager.broadcast_panel_update(
                    snapshot_id=order_flow_id,
                    panel="orderFlow",
                    message_type="orderFlow.update",
                    payload_builder=lambda params: _order_flow_payload(params, order_flow_conn),
                )
        except Exception:
            continue


def _current_options_snapshot():
    service = _ensure_options_service()
    snapshot = service.get_snapshot()
    if snapshot is not None:
        return snapshot
    try:
        return service.refresh_once()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Options realtime cache unavailable: {exc}") from exc


def _ensure_options_service() -> OptionsRealtimeService:
    global _options_service
    if _options_service is None:
        _options_service = OptionsRealtimeService(Settings.from_env())
    return _options_service


def _derive_app_base_url() -> str:
    try:
        return Settings.from_env().derive_app_base_url
    except RuntimeError:
        return os.getenv("DERIVE_APP_BASE_URL", "https://app.derive.xyz")


def _required_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail=f"Missing or invalid field: {key}")
    return value


def _ticker_map_from_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return market_ticker_map_from_payload(payload, _current_ticker_map)


def _ticker_map_for_positions(
    positions: list[dict[str, Any]],
    ticker_map: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    try:
        settings = Settings.from_env()
    except RuntimeError:
        return dict(ticker_map)
    return complete_ticker_map_for_positions(positions, ticker_map, settings=settings)


def _simulation_legs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    legs = payload.get("legs")
    if isinstance(legs, list):
        return legs
    instrument = payload.get("instrumentName") or payload.get("instrument_name")
    if not instrument:
        expiry = str(payload.get("expiry") or "").replace("-", "")
        strike = payload.get("strike")
        option_type = _option_code(payload.get("optionType") or payload.get("option_type"))
        if expiry and strike is not None and option_type:
            instrument = format_option_instrument("HYPE", expiry, float(strike), option_type)
    if not instrument:
        raise HTTPException(status_code=400, detail="Missing or invalid field: legs")
    return [
        {
            "instrumentName": instrument,
            "side": str(payload.get("side") or "buy"),
            "quantity": float(payload.get("quantity") or 1),
        }
    ]


def _current_ticker_map() -> dict[str, dict[str, Any]]:
    service = _options_service
    snapshot = service.get_snapshot() if service is not None else None
    snapshot_map = ticker_map_from_realtime_snapshot(snapshot)
    try:
        with _options_connection() as conn:
            ticker_map = ticker_map_from_latest_database_snapshot(conn)
    except Exception as exc:
        if snapshot_map:
            return snapshot_map
        raise HTTPException(status_code=503, detail=f"Options ticker data unavailable: {exc}") from exc
    return ticker_map or snapshot_map


def _option_code(value: Any) -> str | None:
    return option_type_code(value)


def _panel_payloads(panels: dict[str, dict[str, Any]], order_flow_conn) -> dict[str, Any]:
    service = _ensure_options_service()
    options_panels = {
        panel: params for panel, params in panels.items()
        if panel != "orderFlow"
    }
    payload = service.panel_payloads(options_panels)
    if "orderFlow" in panels:
        payload["orderFlow"] = _order_flow_payload(panels["orderFlow"], order_flow_conn)
    return payload


def _order_flow_payload(params: dict[str, Any], order_flow_conn) -> list[dict[str, Any]]:
    return get_order_flow_events(
        order_flow_conn,
        execution_type=_optional_text(params.get("executionType")),
        leg_structure=_optional_text(params.get("legStructure")),
        option_mix=_optional_text(params.get("optionMix")),
        side=_optional_text(params.get("side")),
        order_type=_optional_text(params.get("orderType")),
        time_in_force=_optional_text(params.get("timeInForce")),
        min_amount=_optional_float(params.get("minAmount")),
        min_premium_usd=_optional_float(params.get("minPremiumUsd")),
        wallet=_optional_text(params.get("wallet")),
        subaccount_id=_optional_text(params.get("subaccountId")),
        limit=_optional_int(params.get("limit"), default=100),
    )


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)
