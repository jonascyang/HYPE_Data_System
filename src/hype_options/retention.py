from __future__ import annotations

from dataclasses import dataclass

MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class RetentionResult:
    raw_payloads: int
    ticker_snapshots: int
    gex_by_strike: int
    collection_runs: int


def run_retention(
    conn,
    *,
    now_ms: int,
    ticker_retention_days: int,
    gex_by_strike_retention_days: int,
    collection_run_retention_days: int = 90,
) -> RetentionResult:
    ticker_cutoff_ms = now_ms - ticker_retention_days * MS_PER_DAY
    gex_cutoff_ms = now_ms - gex_by_strike_retention_days * MS_PER_DAY
    run_cutoff_ms = now_ms - collection_run_retention_days * MS_PER_DAY

    raw_payloads = _delete_count(
        conn,
        "delete from derive_raw_ticker_payloads where expires_at_ms < ?",
        (now_ms,),
    )
    ticker_snapshots = _delete_count(
        conn,
        "delete from derive_ticker_snapshots where ts_ms < ?",
        (ticker_cutoff_ms,),
    )
    gex_by_strike = _delete_count(
        conn,
        "delete from derived_gex_by_strike where ts_ms < ?",
        (gex_cutoff_ms,),
    )
    collection_runs = _delete_count(
        conn,
        "delete from collection_runs where started_ms < ?",
        (run_cutoff_ms,),
    )
    conn.commit()
    return RetentionResult(
        raw_payloads=raw_payloads,
        ticker_snapshots=ticker_snapshots,
        gex_by_strike=gex_by_strike,
        collection_runs=collection_runs,
    )


def _delete_count(conn, sql: str, params: tuple) -> int:
    cursor = conn.execute(sql, params)
    return cursor.rowcount if cursor.rowcount is not None else 0
