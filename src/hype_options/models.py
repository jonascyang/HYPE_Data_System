from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    instrument_name: str
    instrument_type: str
    base_currency: str
    quote_currency: str
    expiry_ts_ms: int
    expiry_yyyymmdd: str
    strike: float
    option_type: str
    is_active: bool
    activation_ts_ms: int | None
    deactivation_ts_ms: int | None
    tick_size: float | None
    min_amount: float | None
    max_amount: float | None
    amount_step: float | None
    maker_fee_rate: float | None
    taker_fee_rate: float | None
    base_asset_address: str | None
    base_asset_sub_id: str | None
    raw_json: str
    first_seen_ms: int
    last_seen_ms: int


@dataclass(frozen=True)
class TickerSnapshot:
    ts_ms: int
    source_ts_ms: int | None
    instrument_name: str
    expiry_ts_ms: int
    expiry_yyyymmdd: str
    strike: float
    option_type: str
    index_price: float | None
    mark_price: float | None
    forward_price: float | None
    bid_price: float | None
    ask_price: float | None
    bid_size: float | None
    ask_size: float | None
    mid_price: float | None
    spread_abs: float | None
    spread_bps: float | None
    mark_iv: float | None
    bid_iv: float | None
    ask_iv: float | None
    delta: float | None
    gamma: float | None
    vega: float | None
    theta: float | None
    rho: float | None
    rate: float | None
    open_interest: float | None
    volume: float | None
    trade_count: int | None
    high_price: float | None
    low_price: float | None
    surface_quality: str
    raw_payload_id: str | None


@dataclass(frozen=True)
class HypePriceSnapshot:
    ts_ms: int
    source: str
    index_name: str
    price: float
    raw_json: str | None


@dataclass(frozen=True)
class ExpiryMetrics:
    ts_ms: int
    expiry_ts_ms: int
    expiry_yyyymmdd: str
    dte_days: float | None
    atm_iv: float | None
    atm_strike: float | None
    call_25d_iv: float | None
    put_25d_iv: float | None
    skew_25d: float | None
    fly_25d: float | None
    total_oi: float
    call_oi: float
    put_oi: float
    put_call_oi_ratio: float | None
    total_volume: float
    call_volume: float
    put_volume: float
    put_call_volume_ratio: float | None
    max_pain_price: float | None
    total_gex: float
    net_gex: float
    abs_gex: float
    model_point_count: int
    tradable_point_count: int


@dataclass(frozen=True)
class GexByStrike:
    ts_ms: int
    expiry_ts_ms: int
    strike: float
    call_gex: float
    put_gex: float
    net_gex: float
    abs_gex: float
    call_oi: float
    put_oi: float


@dataclass(frozen=True)
class GlobalMetrics:
    ts_ms: int
    spot_price: float | None
    rv_1d: float | None
    rv_7d: float | None
    rv_14d: float | None
    rv_30d: float | None
    atm_iv_7d: float | None
    atm_iv_30d: float | None
    atm_iv_60d: float | None
    atm_iv_90d: float | None
    vrp_7d: float | None
    vrp_30d: float | None
    total_option_oi: float
    total_option_volume: float
    call_volume: float
    put_volume: float
    put_call_volume_ratio: float | None
    total_gex: float
    net_gex: float
    abs_gex: float


@dataclass(frozen=True)
class AtmTermMetric:
    ts_ms: int
    tenor: str
    target_dte_days: float
    atm_iv: float | None
    method: str
    left_expiry_yyyymmdd: str | None
    left_dte_days: float | None
    left_atm_iv: float | None
    right_expiry_yyyymmdd: str | None
    right_dte_days: float | None
    right_atm_iv: float | None


@dataclass(frozen=True)
class RawTickerPayload:
    id: str
    ts_ms: int
    expiry_yyyymmdd: str
    row_count: int
    payload_bytes: int | None
    payload_sha256: str
    payload_zstd: bytes
    expires_at_ms: int


@dataclass(frozen=True)
class CollectionRun:
    id: str
    started_ms: int
    finished_ms: int | None
    endpoint: str
    expiry_yyyymmdd: str | None
    status: str
    row_count: int | None
    error_message: str | None
    payload_sha256: str | None
