from __future__ import annotations

import sqlite3
import unittest

from hype_options.db import apply_schema
from hype_options.order_flow import get_order_flow_events
from hype_options.order_flow_collector import collect_order_flow_history_once


class FakeDeriveClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_trade_history(self, **params):
        self.calls.append(params)
        return {
            "result": {
                "pagination": {"count": 2, "num_pages": 1},
                "trades": [
                    {
                        "trade_id": "trade-1",
                        "instrument_name": "HYPE-20260731-95-C",
                        "timestamp": 1_782_733_050_850,
                        "trade_price": "0.68",
                        "trade_amount": "11.1",
                        "direction": "buy",
                        "quote_id": "quote-1",
                        "rfq_id": "rfq-1",
                        "wallet": "0xabc",
                        "subaccount_id": 67182,
                        "tx_status": "settled",
                        "tx_hash": "0xhash",
                        "liquidity_role": "taker",
                    },
                    {
                        "trade_id": "trade-1",
                        "instrument_name": "HYPE-20260731-95-C",
                        "timestamp": 1_782_733_050_850,
                        "trade_price": "0.68",
                        "trade_amount": "11.1",
                        "direction": "sell",
                        "quote_id": "quote-1",
                        "rfq_id": "rfq-1",
                        "wallet": "0xmaker",
                        "subaccount_id": 57643,
                        "tx_status": "settled",
                        "tx_hash": "0xhash",
                        "liquidity_role": "maker",
                    },
                ],
            }
        }


class OrderFlowCollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        apply_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_collect_order_flow_history_once_inserts_public_taker_trades(self) -> None:
        client = FakeDeriveClient()

        result = collect_order_flow_history_once(
            client=client,
            conn=self.conn,
            from_timestamp_ms=1_782_733_000_000,
            to_timestamp_ms=1_782_733_060_000,
            page_size=100,
            max_pages=1,
            observed_at_ms=1_782_733_061_000,
        )

        self.assertEqual(result.fetched_trade_rows, 2)
        self.assertEqual(result.inserted_event_rows, 1)
        self.assertEqual(client.calls[0]["currency"], "HYPE")
        rows = get_order_flow_events(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["executionType"], "RFQ")
        self.assertEqual(rows[0]["wallet"], "0xabc")


if __name__ == "__main__":
    unittest.main()
