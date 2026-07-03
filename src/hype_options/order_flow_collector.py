from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from hype_options.order_flow import (
    insert_order_flow_event,
    normalize_public_trade_history_rows,
)


DEFAULT_LOOKBACK_SECONDS = 3600
DEFAULT_OVERLAP_MS = 5 * 60 * 1000


@dataclass(frozen=True)
class OrderFlowCollectionResult:
    fetched_trade_rows: int
    inserted_event_rows: int
    skipped_trade_rows: int
    from_timestamp_ms: int
    to_timestamp_ms: int
    pages_fetched: int


def collect_order_flow_history_once(
    *,
    client,
    conn,
    currency: str = "HYPE",
    from_timestamp_ms: int | None = None,
    to_timestamp_ms: int | None = None,
    page_size: int = 1000,
    max_pages: int = 1,
    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
    observed_at_ms: int | None = None,
) -> OrderFlowCollectionResult:
    observed_at_ms = observed_at_ms or int(time.time() * 1000)
    to_timestamp_ms = to_timestamp_ms or observed_at_ms
    from_timestamp_ms = from_timestamp_ms or _default_from_timestamp_ms(
        conn,
        to_timestamp_ms=to_timestamp_ms,
        lookback_seconds=lookback_seconds,
    )

    fetched_trade_rows = 0
    inserted_event_rows = 0
    accepted_trade_rows = 0
    pages_fetched = 0

    for page in range(1, max(1, max_pages) + 1):
        payload = client.get_trade_history(
            currency=currency,
            instrument_type="option",
            from_timestamp=from_timestamp_ms,
            to_timestamp=to_timestamp_ms,
            page=page,
            page_size=max(1, min(page_size, 1000)),
            tx_status="settled",
        )
        result = payload.get("result") or {}
        trades = result.get("trades") or []
        pages_fetched += 1
        fetched_trade_rows += len(trades)

        normalized_events = normalize_public_trade_history_rows(
            [row for row in trades if isinstance(row, dict)],
            observed_at_ms=observed_at_ms,
        )
        for normalized in normalized_events:
            insert_order_flow_event(conn, normalized)
            inserted_event_rows += 1
            accepted_trade_rows += len(normalized.legs)

        pagination = result.get("pagination") or {}
        num_pages = _int(pagination.get("num_pages"))
        if not trades or (num_pages is not None and page >= num_pages):
            break

    return OrderFlowCollectionResult(
        fetched_trade_rows=fetched_trade_rows,
        inserted_event_rows=inserted_event_rows,
        skipped_trade_rows=fetched_trade_rows - accepted_trade_rows,
        from_timestamp_ms=from_timestamp_ms,
        to_timestamp_ms=to_timestamp_ms,
        pages_fetched=pages_fetched,
    )


def _default_from_timestamp_ms(conn, *, to_timestamp_ms: int, lookback_seconds: int) -> int:
    row = conn.execute("SELECT max(trade_ts_ms) FROM derive_order_flow_events").fetchone()
    latest_ts_ms = row[0] if row and row[0] is not None else None
    if latest_ts_ms is not None:
        return max(0, int(latest_ts_ms) - DEFAULT_OVERLAP_MS)
    return max(0, to_timestamp_ms - max(1, lookback_seconds) * 1000)


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
