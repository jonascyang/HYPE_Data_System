#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hype_options.collector import collect_from_payloads
from hype_options.derive_client import DeriveClient, expiry_to_yyyymmdd


def active_expiries(instruments_payload: dict[str, Any]) -> list[str]:
    expiries: set[str] = set()
    for item in instruments_payload.get("result", []):
        if not item.get("is_active"):
            continue
        option_details = item.get("option_details") or {}
        expiry = option_details.get("expiry")
        if expiry is not None:
            expiries.add(expiry_to_yyyymmdd(int(expiry)))
    return sorted(expiries)


def rows(items: list[Any], *, limit: int | None = None) -> list[dict[str, Any]]:
    selected = items if limit is None or limit <= 0 else items[:limit]
    return [asdict(item) for item in selected]


def runtime_iv_curve(items: list[Any], *, limit: int | None = None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float], dict[str, Any]] = {}
    for row in sorted(items, key=lambda item: (item.expiry_ts_ms, item.strike, item.option_type)):
        if row.surface_quality == "invalid" or row.mark_iv is None:
            continue
        key = (row.expiry_yyyymmdd, row.strike)
        point = grouped.setdefault(
            key,
            {
                "expiry": row.expiry_yyyymmdd,
                "strike": row.strike,
                "callIv": None,
                "putIv": None,
                "callDelta": None,
                "putDelta": None,
                "callOi": 0.0,
                "putOi": 0.0,
            },
        )
        if row.option_type == "C":
            point["callIv"] = row.mark_iv
            point["callDelta"] = row.delta
            point["callOi"] = row.open_interest or 0.0
        elif row.option_type == "P":
            point["putIv"] = row.mark_iv
            point["putDelta"] = row.delta
            point["putOi"] = row.open_interest or 0.0
    values = list(grouped.values())
    return values if limit is None or limit <= 0 else values[:limit]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    client = DeriveClient(base_url=args.base_url, currency=args.currency)
    snapshot_ms = int(time.time() * 1000)

    instruments_payload = client.get_instruments()
    expiries = active_expiries(instruments_payload)
    if args.expiry_limit is not None:
        expiries = expiries[: args.expiry_limit]

    ticker_payloads = {expiry: client.get_tickers(expiry) for expiry in expiries}
    result = collect_from_payloads(
        instruments_payload=instruments_payload,
        ticker_payloads_by_expiry=ticker_payloads,
        snapshot_ms=snapshot_ms,
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": {
            "base_url": args.base_url,
            "currency": args.currency,
            "instrument_endpoint": "/public/get_instruments",
            "ticker_endpoint": "/public/get_tickers",
        },
        "collection": {
            "snapshot_ms": snapshot_ms,
            "requested_expiries": expiries,
            "instrument_rows": result.instrument_row_count,
            "active_instruments": result.active_instrument_count,
            "ticker_rows": result.ticker_row_count,
            "expiry_metrics": result.expiry_metric_count,
            "atm_term_metrics": result.atm_term_metric_count,
            "gex_by_strike": result.gex_by_strike_count,
            "global_metrics": result.global_metric_count,
        },
        "expiry_metrics": rows(result.expiry_metrics),
        "atm_term_metrics": rows(result.atm_term_metrics),
        "global_metrics": rows(result.global_metrics),
        "iv_curve": runtime_iv_curve(result.ticker_rows, limit=args.row_limit),
        "gex_by_strike": rows(result.gex_by_strike, limit=args.row_limit),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect one public Derive HYPE options snapshot and write derived metrics to JSON."
    )
    parser.add_argument("--base-url", default="https://api.lyra.finance")
    parser.add_argument("--currency", default="HYPE")
    parser.add_argument("--expiry-limit", type=int, default=3)
    parser.add_argument("--row-limit", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("output/options_collect_once.json"))
    args = parser.parse_args()

    payload = build_payload(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")

    collection = payload["collection"]
    print(f"written: {args.output}")
    print(f"requested expiries: {len(collection['requested_expiries'])}")
    print(f"active instruments: {collection['active_instruments']}")
    print(f"ticker rows: {collection['ticker_rows']}")
    print(f"expiry metrics: {collection['expiry_metrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
