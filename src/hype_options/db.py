from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from hype_options.models import (
    AtmTermMetric,
    CollectionRun,
    ExpiryMetrics,
    GexByStrike,
    GlobalMetrics,
    HypePriceSnapshot,
    Instrument,
    RawTickerPayload,
    TickerSnapshot,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
OPTIONS_HISTORY_SCHEMA_PATH = Path(__file__).with_name("options_history_schema.sql")
ORDER_FLOW_SCHEMA_PATH = Path(__file__).with_name("order_flow_schema.sql")
DEFAULT_MAX_SQL_VARIABLES = 30_000


def schema_sql() -> str:
    return SCHEMA_PATH.read_text()


def options_history_schema_sql() -> str:
    return OPTIONS_HISTORY_SCHEMA_PATH.read_text()


def order_flow_schema_sql() -> str:
    return ORDER_FLOW_SCHEMA_PATH.read_text()


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(schema_sql())
    _ensure_column(conn, "derive_order_flow_events", "wallet", "TEXT")
    conn.commit()


def apply_options_history_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(options_history_schema_sql())
    conn.commit()


def apply_order_flow_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(order_flow_schema_sql())
    _ensure_column(conn, "derive_order_flow_events", "wallet", "TEXT")
    conn.commit()


def connect_database(database_url: str, auth_token: str = ""):
    if database_url.startswith("sqlite:///"):
        return _connect_sqlite(database_url)

    import libsql

    return libsql.connect(database=database_url, auth_token=auth_token)


def connect_turso(database_url: str, auth_token: str):
    return connect_database(database_url, auth_token)


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _connect_sqlite(database_url: str) -> sqlite3.Connection:
    path = database_url.removeprefix("sqlite:///")
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(Path(path).expanduser() if path != ":memory:" else path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class Repository:
    def __init__(self, conn: sqlite3.Connection, max_sql_variables: int = DEFAULT_MAX_SQL_VARIABLES):
        self.conn = conn
        self.max_sql_variables = max_sql_variables

    def upsert_instruments(self, rows: list[Instrument]) -> None:
        if not rows:
            return
        columns = [
            "instrument_name",
            "instrument_type",
            "base_currency",
            "quote_currency",
            "expiry_ts_ms",
            "expiry_yyyymmdd",
            "strike",
            "option_type",
            "is_active",
            "activation_ts_ms",
            "deactivation_ts_ms",
            "tick_size",
            "min_amount",
            "max_amount",
            "amount_step",
            "maker_fee_rate",
            "taker_fee_rate",
            "base_asset_address",
            "base_asset_sub_id",
            "raw_json",
            "first_seen_ms",
            "last_seen_ms",
        ]
        conflict_clause = """
        ON CONFLICT(instrument_name) DO UPDATE SET
          is_active = excluded.is_active,
          raw_json = excluded.raw_json,
          last_seen_ms = excluded.last_seen_ms
        """
        self._insert_many_values(
            insert_head="INSERT INTO derive_instruments",
            columns=columns,
            rows=rows,
            conflict_clause=conflict_clause,
        )

    def insert_ticker_snapshots(self, rows: list[TickerSnapshot]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derive_ticker_snapshots", rows)

    def insert_expiry_metrics(self, rows: list[ExpiryMetrics]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derived_expiry_metrics", rows)

    def insert_atm_term_metrics(self, rows: list[AtmTermMetric]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derived_atm_term_metrics", rows)

    def insert_price_snapshots(self, rows: list[HypePriceSnapshot]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO hype_price_snapshots", rows)

    def insert_gex_by_strike(self, rows: list[GexByStrike]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derived_gex_by_strike", rows)

    def insert_global_metrics(self, rows: list[GlobalMetrics]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derived_global_metrics", rows)

    def insert_raw_ticker_payloads(self, rows: list[RawTickerPayload]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO derive_raw_ticker_payloads", rows)

    def insert_collection_runs(self, rows: list[CollectionRun]) -> None:
        self._insert_dataclass_rows("INSERT OR REPLACE INTO collection_runs", rows)

    def price_snapshots_since(self, ts_ms: int) -> list[dict]:
        cursor = self.conn.execute(
            """
            SELECT ts_ms, price
            FROM hype_price_snapshots
            WHERE ts_ms >= ?
            ORDER BY ts_ms
            """,
            (ts_ms,),
        )
        return [{"ts_ms": row[0], "price": row[1]} for row in cursor.fetchall()]

    def _insert_dataclass_rows(self, insert_head: str, rows: list[Any]) -> None:
        if not rows:
            return
        columns = list(asdict(rows[0]).keys())
        self._insert_many_values(insert_head=insert_head, columns=columns, rows=rows)

    def _insert_many_values(
        self,
        *,
        insert_head: str,
        columns: list[str],
        rows: list[Any],
        conflict_clause: str = "",
    ) -> None:
        row_values = [_row_values(row, columns) for row in rows]
        row_placeholder = f"({', '.join('?' for _ in columns)})"
        max_rows_per_statement = max(1, self.max_sql_variables // len(columns))

        for chunk in _chunks(row_values, max_rows_per_statement):
            placeholders = ", ".join(row_placeholder for _ in chunk)
            sql = f"""
            {insert_head} ({", ".join(columns)})
            VALUES {placeholders}
            {conflict_clause}
            """
            params = tuple(value for row in chunk for value in row)
            self.conn.execute(sql, params)
        self.conn.commit()


def _row_dict(row: Any) -> dict[str, Any]:
    data = asdict(row)
    for key, value in data.items():
        if isinstance(value, bool):
            data[key] = int(value)
    return data


def _row_values(row: Any, columns: list[str]) -> tuple[Any, ...]:
    data = _row_dict(row)
    return tuple(data[column] for column in columns)


def _chunks(values: list[tuple[Any, ...]], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]
