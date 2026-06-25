from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

import zstandard as zstd

from hype_options.metrics import compute_atm_term_metrics, compute_expiry_metrics, compute_gex_by_strike
from hype_options.metrics import compute_global_metrics
from hype_options.models import CollectionRun, HypePriceSnapshot, Instrument, RawTickerPayload
from hype_options.models import TickerSnapshot
from hype_options.normalizer import normalize_instruments, normalize_tickers


@dataclass(frozen=True)
class CollectionResult:
    instrument_row_count: int
    active_instrument_count: int
    ticker_row_count: int
    expiry_count: int
    expiry_metric_count: int
    atm_term_metric_count: int
    price_snapshot_count: int
    gex_by_strike_count: int
    global_metric_count: int
    raw_payload_count: int
    collection_run_count: int
    instrument_rows: list[Instrument]
    ticker_rows: list[TickerSnapshot]
    expiry_metrics: list
    atm_term_metrics: list
    price_snapshots: list[HypePriceSnapshot]
    gex_by_strike: list
    global_metrics: list
    raw_payloads: list[RawTickerPayload]
    collection_runs: list[CollectionRun]


def collect_from_payloads(
    *,
    instruments_payload: dict,
    ticker_payloads_by_expiry: dict[str, dict],
    snapshot_ms: int,
    raw_payload_retention_days: int = 7,
) -> CollectionResult:
    instruments = normalize_instruments(instruments_payload, seen_ms=snapshot_ms)
    active = [item for item in instruments if item.is_active]
    expiry_lookup = {item.expiry_yyyymmdd: item.expiry_ts_ms for item in active}

    ticker_rows: list[TickerSnapshot] = []
    raw_payloads: list[RawTickerPayload] = []
    collection_runs: list[CollectionRun] = []
    for expiry_yyyymmdd, payload in ticker_payloads_by_expiry.items():
        raw_payload = build_raw_ticker_payload(
            expiry_yyyymmdd=expiry_yyyymmdd,
            payload=payload,
            ts_ms=snapshot_ms,
            retention_days=raw_payload_retention_days,
        )
        raw_payloads.append(raw_payload)
        collection_runs.append(
            CollectionRun(
                id=f"{snapshot_ms}:get_tickers:{expiry_yyyymmdd}",
                started_ms=snapshot_ms,
                finished_ms=snapshot_ms,
                endpoint="/public/get_tickers",
                expiry_yyyymmdd=expiry_yyyymmdd,
                status="ok",
                row_count=raw_payload.row_count,
                error_message=None,
                payload_sha256=raw_payload.payload_sha256,
            )
        )
        expiry_ts_ms = expiry_lookup[expiry_yyyymmdd]
        ticker_rows.extend(
            normalize_tickers(
                payload,
                expiry_ts_ms=expiry_ts_ms,
                expiry_yyyymmdd=expiry_yyyymmdd,
                snapshot_ms=snapshot_ms,
                raw_payload_id=raw_payload.id,
            )
        )

    spot_price = _spot_price(ticker_rows)
    expiry_metrics = (
        compute_expiry_metrics(ticker_rows, ts_ms=snapshot_ms, spot_price=spot_price)
        if spot_price is not None
        else []
    )
    atm_term_metrics = (
        compute_atm_term_metrics(expiry_metrics, ts_ms=snapshot_ms) if expiry_metrics else []
    )
    price_snapshots = (
        [
            HypePriceSnapshot(
                ts_ms=snapshot_ms,
                source="derive_ticker_index",
                index_name="HYPE",
                price=spot_price,
                raw_json=json.dumps({"spot_price": spot_price}, separators=(",", ":")),
            )
        ]
        if spot_price is not None
        else []
    )
    gex_by_strike = (
        compute_gex_by_strike(ticker_rows, ts_ms=snapshot_ms, spot_price=spot_price)
        if spot_price is not None
        else []
    )
    global_metric = (
        compute_global_metrics(
            expiry_metrics=expiry_metrics,
            price_points=[{"ts_ms": snapshot_ms, "price": spot_price}],
            ts_ms=snapshot_ms,
            spot_price=spot_price,
        )
        if spot_price is not None
        else None
    )
    global_metrics = [global_metric] if global_metric is not None else []

    return CollectionResult(
        instrument_row_count=len(instruments),
        active_instrument_count=len(active),
        ticker_row_count=len(ticker_rows),
        expiry_count=len({row.expiry_ts_ms for row in ticker_rows}),
        expiry_metric_count=len(expiry_metrics),
        atm_term_metric_count=len(atm_term_metrics),
        price_snapshot_count=len(price_snapshots),
        gex_by_strike_count=len(gex_by_strike),
        global_metric_count=len(global_metrics),
        raw_payload_count=len(raw_payloads),
        collection_run_count=len(collection_runs),
        instrument_rows=instruments,
        ticker_rows=ticker_rows,
        expiry_metrics=expiry_metrics,
        atm_term_metrics=atm_term_metrics,
        price_snapshots=price_snapshots,
        gex_by_strike=gex_by_strike,
        global_metrics=global_metrics,
        raw_payloads=raw_payloads,
        collection_runs=collection_runs,
    )


def collect_live_once(
    *,
    client,
    repository,
    snapshot_ms: int | None = None,
    expiry_limit: int | None = None,
    raw_payload_retention_days: int = 7,
) -> CollectionResult:
    snapshot_ms = snapshot_ms or int(time.time() * 1000)
    instruments_payload = client.get_instruments()
    instruments = normalize_instruments(instruments_payload, seen_ms=snapshot_ms)
    active = [item for item in instruments if item.is_active]
    expiries = sorted({item.expiry_yyyymmdd for item in active})
    if expiry_limit is not None:
        expiries = expiries[:expiry_limit]

    ticker_payloads = {expiry: client.get_tickers(expiry) for expiry in expiries}
    result = collect_from_payloads(
        instruments_payload=instruments_payload,
        ticker_payloads_by_expiry=ticker_payloads,
        snapshot_ms=snapshot_ms,
        raw_payload_retention_days=raw_payload_retention_days,
    )

    repository.upsert_instruments(result.instrument_rows)
    repository.insert_price_snapshots(result.price_snapshots)
    repository.insert_raw_ticker_payloads(result.raw_payloads)
    repository.insert_ticker_snapshots(result.ticker_rows)
    repository.insert_expiry_metrics(result.expiry_metrics)
    repository.insert_atm_term_metrics(result.atm_term_metrics)
    repository.insert_gex_by_strike(result.gex_by_strike)
    repository.insert_global_metrics(
        _global_metrics_with_price_history(
            repository=repository,
            result=result,
            snapshot_ms=snapshot_ms,
            spot_price=_spot_price(result.ticker_rows),
        )
        or result.global_metrics
    )
    repository.insert_collection_runs(result.collection_runs)
    return result


def build_raw_ticker_payload(
    *,
    expiry_yyyymmdd: str,
    payload: dict,
    ts_ms: int,
    retention_days: int = 7,
) -> RawTickerPayload:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    row_count = len(payload.get("result", {}).get("tickers", {}))
    return RawTickerPayload(
        id=f"{ts_ms}:ticker:{expiry_yyyymmdd}:{payload_sha256[:16]}",
        ts_ms=ts_ms,
        expiry_yyyymmdd=expiry_yyyymmdd,
        row_count=row_count,
        payload_bytes=len(payload_bytes),
        payload_sha256=payload_sha256,
        payload_zstd=zstd.ZstdCompressor(level=3).compress(payload_bytes),
        expires_at_ms=ts_ms + retention_days * 86_400_000,
    )


def _spot_price(rows: list[TickerSnapshot]) -> float | None:
    for row in rows:
        if row.index_price is not None:
            return row.index_price
    return None


def _global_metrics_with_price_history(
    *,
    repository,
    result: CollectionResult,
    snapshot_ms: int,
    spot_price: float | None,
):
    if spot_price is None:
        return []
    try:
        price_points = repository.price_snapshots_since(snapshot_ms - 31 * 86_400_000)
    except AttributeError:
        return []
    if not any(point["ts_ms"] == snapshot_ms for point in price_points):
        price_points.append({"ts_ms": snapshot_ms, "price": spot_price})
    global_metric = compute_global_metrics(
        expiry_metrics=result.expiry_metrics,
        price_points=price_points,
        ts_ms=snapshot_ms,
        spot_price=spot_price,
    )
    return [global_metric] if global_metric is not None else []
