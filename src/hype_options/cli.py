from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from hype_options.collector import collect_live_once
from hype_options.config import Settings
from hype_options.dashboard_data import write_dashboard_payload
from hype_options.db import (
    Repository,
    apply_options_history_schema,
    apply_order_flow_schema,
    apply_schema,
    connect_database,
)
from hype_options.derive_client import DeriveClient
from hype_options.order_flow_collector import collect_order_flow_history_once
from hype_options.retention import run_retention


def run_collect_loop(
    *,
    collect_once: Callable[[], object],
    interval_seconds: int,
    max_runs: int | None = None,
    sleep: Callable[[int], None] = time.sleep,
) -> None:
    runs = 0
    while max_runs is None or runs < max_runs:
        collect_once()
        runs += 1
        if max_runs is not None and runs >= max_runs:
            break
        sleep(interval_seconds)


def format_collection_summary(result) -> str:
    lines = [
        f"active instruments: {result.active_instrument_count}",
        f"active expiries: {result.expiry_count}",
        f"ticker rows: {result.ticker_row_count}",
        f"expiry metrics: {result.expiry_metric_count}",
        f"raw payloads: {result.raw_payload_count}",
        f"price snapshots: {result.price_snapshot_count}",
        f"atm term metrics: {result.atm_term_metric_count}",
        f"gex by strike rows: {result.gex_by_strike_count}",
        f"global metrics: {result.global_metric_count}",
    ]
    return "\n".join(lines)


def format_order_flow_collection_summary(result) -> str:
    lines = [
        f"order flow fetched trade rows: {result.fetched_trade_rows}",
        f"order flow inserted events: {result.inserted_event_rows}",
        f"order flow skipped rows: {result.skipped_trade_rows}",
        f"order flow pages fetched: {result.pages_fetched}",
        f"from timestamp ms: {result.from_timestamp_ms}",
        f"to timestamp ms: {result.to_timestamp_ms}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hype_options.cli")
    parser.add_argument("--env-file", default=".env.local")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db")
    init_parser.add_argument(
        "--target",
        choices=["options-history", "order-flow", "full"],
        default="options-history",
    )

    dry_run_parser = subparsers.add_parser("dry-run-live")
    dry_run_parser.add_argument("--expiry-limit", type=int, default=None)

    once_parser = subparsers.add_parser("collect-once")
    once_parser.add_argument("--expiry-limit", type=int, default=None)

    order_flow_once_parser = subparsers.add_parser("collect-order-flow-once")
    order_flow_once_parser.add_argument("--from-timestamp-ms", type=int, default=None)
    order_flow_once_parser.add_argument("--to-timestamp-ms", type=int, default=None)
    order_flow_once_parser.add_argument("--lookback-seconds", type=int, default=3600)
    order_flow_once_parser.add_argument("--page-size", type=int, default=1000)
    order_flow_once_parser.add_argument("--max-pages", type=int, default=1)

    order_flow_loop_parser = subparsers.add_parser("collect-order-flow-loop")
    order_flow_loop_parser.add_argument("--interval-seconds", type=int, default=None)
    order_flow_loop_parser.add_argument("--max-runs", type=int, default=None)
    order_flow_loop_parser.add_argument("--lookback-seconds", type=int, default=3600)
    order_flow_loop_parser.add_argument("--page-size", type=int, default=1000)
    order_flow_loop_parser.add_argument("--max-pages", type=int, default=1)

    loop_parser = subparsers.add_parser("collect-loop")
    loop_parser.add_argument("--interval-seconds", type=int, default=None)
    loop_parser.add_argument("--max-runs", type=int, default=None)
    loop_parser.add_argument("--expiry-limit", type=int, default=None)

    retention_parser = subparsers.add_parser("retention")
    retention_parser.add_argument("--ticker-retention-days", type=int, default=None)
    retention_parser.add_argument("--gex-by-strike-retention-days", type=int, default=None)
    retention_parser.add_argument("--collection-run-retention-days", type=int, default=None)

    serve_parser = subparsers.add_parser("serve-dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    export_parser = subparsers.add_parser("export-dashboard-data")
    export_parser.add_argument("--output", type=Path, default=Path("output/dashboard.json"))
    export_parser.add_argument("--history-days", type=int, default=90)

    args = parser.parse_args(argv)
    load_dotenv(args.env_file)

    if args.command == "serve-dashboard":
        import uvicorn

        uvicorn.run(
            "hype_options.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0

    if args.command == "dry-run-live":
        client = DeriveClient(
            base_url=os.getenv("DERIVE_BASE_URL", "https://api.lyra.finance"),
            currency=os.getenv("DERIVE_CURRENCY", "HYPE"),
        )
        result = collect_live_once(
            client=client,
            repository=_NoopRepository(),
            expiry_limit=args.expiry_limit,
            raw_payload_retention_days=int(os.getenv("RAW_PAYLOAD_RETENTION_DAYS", "3")),
        )
        print(format_collection_summary(result))
        return 0

    settings = Settings.from_env()

    if args.command == "init-db":
        if args.target == "order-flow":
            conn = connect_database(
                settings.order_flow_database_url,
                settings.order_flow_database_auth_token,
            )
        else:
            conn = connect_database(settings.database_url, settings.database_auth_token)
        try:
            if args.target == "options-history":
                apply_options_history_schema(conn)
            elif args.target == "order-flow":
                apply_order_flow_schema(conn)
            else:
                apply_schema(conn)
        finally:
            conn.close()
        print(f"schema applied: {args.target}")
        return 0

    def collect_once():
        client = DeriveClient(
            base_url=settings.derive_base_url,
            currency=settings.derive_currency,
        )
        conn = connect_database(settings.database_url, settings.database_auth_token)
        try:
            result = collect_live_once(
                client=client,
                repository=Repository(conn),
                expiry_limit=getattr(args, "expiry_limit", None),
                raw_payload_retention_days=settings.raw_payload_retention_days,
            )
            print(format_collection_summary(result))
            return result
        finally:
            conn.close()

    if args.command == "collect-once":
        collect_once()
        return 0

    def collect_order_flow_once():
        client = DeriveClient(
            base_url=settings.derive_base_url,
            currency=settings.derive_currency,
        )
        conn = connect_database(
            settings.order_flow_database_url,
            settings.order_flow_database_auth_token,
        )
        try:
            apply_order_flow_schema(conn)
            result = collect_order_flow_history_once(
                client=client,
                conn=conn,
                currency=settings.derive_currency,
                from_timestamp_ms=getattr(args, "from_timestamp_ms", None),
                to_timestamp_ms=getattr(args, "to_timestamp_ms", None),
                lookback_seconds=args.lookback_seconds,
                page_size=args.page_size,
                max_pages=args.max_pages,
            )
            print(format_order_flow_collection_summary(result))
            return result
        finally:
            conn.close()

    if args.command == "collect-order-flow-once":
        collect_order_flow_once()
        return 0

    if args.command == "collect-order-flow-loop":
        interval_seconds = args.interval_seconds or settings.derive_collection_interval_seconds
        run_collect_loop(
            collect_once=collect_order_flow_once,
            interval_seconds=interval_seconds,
            max_runs=args.max_runs,
        )
        return 0

    if args.command == "collect-loop":
        interval_seconds = args.interval_seconds or settings.derive_collection_interval_seconds
        run_collect_loop(
            collect_once=collect_once,
            interval_seconds=interval_seconds,
            max_runs=args.max_runs,
        )
        return 0

    if args.command == "retention":
        conn = connect_database(settings.database_url, settings.database_auth_token)
        try:
            result = run_retention(
                conn,
                now_ms=int(time.time() * 1000),
                ticker_retention_days=args.ticker_retention_days
                or settings.ticker_retention_days,
                gex_by_strike_retention_days=args.gex_by_strike_retention_days
                or settings.gex_by_strike_retention_days,
                collection_run_retention_days=args.collection_run_retention_days
                or settings.collection_run_retention_days,
            )
        finally:
            conn.close()
        print(
            "retention "
            f"raw_payloads={result.raw_payloads} "
            f"ticker_snapshots={result.ticker_snapshots} "
            f"gex_by_strike={result.gex_by_strike} "
            f"collection_runs={result.collection_runs}"
        )
        return 0

    if args.command == "export-dashboard-data":
        conn = connect_database(settings.database_url, settings.database_auth_token)
        try:
            payload = write_dashboard_payload(
                conn,
                args.output,
                history_days=args.history_days,
            )
        finally:
            conn.close()
        print(f"dashboard data written: {args.output}")
        print(f"snapshot: {payload.get('snapshotLabel')}")
        print(f"expiries: {len(payload.get('expiryMetrics', []))}")
        print(f"vrp points: {len(payload.get('vrpHistory', []))}")
        return 0

    return 1


class _NoopRepository:
    def __getattr__(self, name):
        if name == "price_snapshots_since":
            return lambda ts_ms: []
        if name.startswith(("insert_", "upsert_")):
            return lambda rows: None
        raise AttributeError(name)


if __name__ == "__main__":
    raise SystemExit(main())
