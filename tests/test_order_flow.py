from __future__ import annotations

import sqlite3
import unittest

from hype_options.db import apply_schema
from hype_options.order_flow import (
    get_order_flow_events,
    normalize_order_flow_event,
    normalize_public_trade_history_row,
    normalize_public_trade_history_rows,
)


class OrderFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        apply_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_normalizes_orderbook_order_as_single_call_event(self) -> None:
        normalized = normalize_order_flow_event(
            {
                "source_endpoint": "private/order",
                "external_event_id": "order-1",
                "event_kind": "order",
                "trade_ts_ms": 1_782_592_800_000,
                "instrument_name": "HYPE-20260703-75-C",
                "side": "buy",
                "side_source": "official_direction",
                "amount": 1250,
                "price": 2.4,
                "premium_usd": 3000,
                "order_type": "limit",
                "time_in_force": "post_only",
                "subaccount_id": "sub-1",
            },
            observed_at_ms=1_782_592_801_000,
        )

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.event["execution_type"], "ORDERBOOK_ORDER")
        self.assertEqual(normalized.event["leg_structure"], "SINGLE_LEG")
        self.assertEqual(normalized.event["option_mix"], "CALL")
        self.assertEqual(normalized.event["order_type"], "limit")
        self.assertEqual(normalized.event["time_in_force"], "post_only")
        self.assertEqual(len(normalized.legs), 1)
        self.assertEqual(normalized.legs[0]["option_type"], "call")
        self.assertEqual(normalized.legs[0]["expiry"], "2026-07-03")
        self.assertEqual(normalized.legs[0]["strike"], 75.0)

    def test_normalizes_orderbook_order_with_underscore_decimal_strike(self) -> None:
        normalized = normalize_order_flow_event(
            {
                "source_endpoint": "private/order",
                "external_event_id": "order-decimal",
                "event_kind": "order",
                "trade_ts_ms": 1_782_592_800_000,
                "instrument_name": "HYPE-20260703-75_5-C",
                "side": "buy",
                "side_source": "official_direction",
                "amount": 1250,
                "price": 2.4,
                "premium_usd": 3000,
                "order_type": "limit",
                "time_in_force": "post_only",
            },
            observed_at_ms=1_782_592_801_000,
        )

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.legs[0]["option_type"], "call")
        self.assertEqual(normalized.legs[0]["expiry"], "2026-07-03")
        self.assertEqual(normalized.legs[0]["strike"], 75.5)

    def test_normalizes_multi_leg_rfq_as_both_event(self) -> None:
        normalized = normalize_order_flow_event(
            {
                "source_endpoint": "execute_quote",
                "external_event_id": "quote-1",
                "event_kind": "execute_quote",
                "trade_ts_ms": 1_782_592_800_000,
                "side": "unknown",
                "side_source": "unavailable",
                "rfq_id": "rfq-1",
                "quote_id": "quote-1",
                "legs": [
                    {
                        "instrument_name": "HYPE-20260703-75-C",
                        "side": "buy",
                        "amount": 1250,
                        "price": 2.1,
                        "premium_usd": 2625,
                    },
                    {
                        "instrument_name": "HYPE-20260703-60-P",
                        "side": "sell",
                        "amount": 1250,
                        "price": 1.4,
                        "premium_usd": 1750,
                    },
                ],
            },
            observed_at_ms=1_782_592_801_000,
        )

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.event["execution_type"], "RFQ")
        self.assertEqual(normalized.event["leg_structure"], "MULTI_LEG")
        self.assertEqual(normalized.event["option_mix"], "BOTH")
        self.assertIsNone(normalized.event["order_type"])
        self.assertIsNone(normalized.event["time_in_force"])
        self.assertEqual([leg["option_type"] for leg in normalized.legs], ["call", "put"])

    def test_rejects_unclassifiable_event(self) -> None:
        normalized = normalize_order_flow_event(
            {
                "source_endpoint": "public/trades",
                "external_event_id": "trade-1",
                "event_kind": "trade",
                "instrument_name": "HYPE-20260703-75-C",
            },
            observed_at_ms=1_782_592_801_000,
        )

        self.assertIsNone(normalized)

    def test_normalizes_public_trade_history_row_as_rfq_taker_event(self) -> None:
        normalized = normalize_public_trade_history_row(
            {
                "trade_id": "trade-1",
                "instrument_name": "HYPE-20260731-95-C",
                "timestamp": 1_782_733_050_850,
                "trade_price": "0.68",
                "trade_amount": "11.1",
                "direction": "sell",
                "quote_id": "quote-1",
                "rfq_id": "rfq-1",
                "wallet": "0xabc",
                "subaccount_id": 67182,
                "tx_status": "settled",
                "tx_hash": "0xhash",
                "liquidity_role": "taker",
            },
            observed_at_ms=1_782_733_051_000,
        )

        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized.event["source_endpoint"], "public/get_trade_history")
        self.assertEqual(normalized.event["external_event_id"], "quote:quote-1:67182")
        self.assertEqual(normalized.event["execution_type"], "RFQ")
        self.assertEqual(normalized.event["side"], "sell")
        self.assertEqual(normalized.event["side_source"], "taker_direction")
        self.assertEqual(normalized.event["wallet"], "0xabc")
        self.assertEqual(normalized.event["premium_usd"], 7.548)
        self.assertEqual(normalized.legs[0]["instrument_name"], "HYPE-20260731-95-C")

    def test_groups_public_trade_history_rfq_rows_by_quote_and_participant(self) -> None:
        normalized = normalize_public_trade_history_rows(
            [
                {
                    "trade_id": "trade-1",
                    "instrument_name": "HYPE-20260731-90-C",
                    "timestamp": 1_782_733_050_850,
                    "trade_price": "5",
                    "trade_amount": "2",
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
                    "trade_id": "trade-2",
                    "instrument_name": "HYPE-20260731-80-P",
                    "timestamp": 1_782_733_050_850,
                    "trade_price": "3",
                    "trade_amount": "2",
                    "direction": "sell",
                    "quote_id": "quote-1",
                    "rfq_id": "rfq-1",
                    "wallet": "0xabc",
                    "subaccount_id": 67182,
                    "tx_status": "settled",
                    "tx_hash": "0xhash",
                    "liquidity_role": "taker",
                },
                {
                    "trade_id": "trade-3",
                    "instrument_name": "HYPE-20260731-90-C",
                    "timestamp": 1_782_733_050_850,
                    "trade_price": "5",
                    "trade_amount": "2",
                    "direction": "sell",
                    "quote_id": "quote-1",
                    "rfq_id": "rfq-1",
                    "wallet": "0xmaker",
                    "subaccount_id": 1,
                    "liquidity_role": "maker",
                },
            ],
            observed_at_ms=1_782_733_051_000,
        )

        self.assertEqual(len(normalized), 1)
        event = normalized[0]
        self.assertEqual(event.event["external_event_id"], "quote:quote-1:67182")
        self.assertEqual(event.event["execution_type"], "RFQ")
        self.assertEqual(event.event["leg_structure"], "MULTI_LEG")
        self.assertEqual(event.event["option_mix"], "BOTH")
        self.assertEqual(event.event["side"], "unknown")
        self.assertEqual(event.event["amount"], 4.0)
        self.assertEqual(event.event["premium_usd"], 16.0)
        self.assertEqual([leg["instrument_name"] for leg in event.legs], ["HYPE-20260731-90-C", "HYPE-20260731-80-P"])
        self.assertEqual([leg["side"] for leg in event.legs], ["buy", "sell"])

    def test_skips_public_trade_history_maker_row_by_default(self) -> None:
        normalized = normalize_public_trade_history_row(
            {
                "trade_id": "trade-1",
                "instrument_name": "HYPE-20260731-95-C",
                "timestamp": 1_782_733_050_850,
                "trade_price": "0.68",
                "trade_amount": "11.1",
                "direction": "buy",
                "liquidity_role": "maker",
            },
            observed_at_ms=1_782_733_051_000,
        )

        self.assertIsNone(normalized)


    def test_get_order_flow_events_hides_legacy_single_rfq_when_grouped_quote_exists(self) -> None:
        self.conn.executemany(
            """
            INSERT INTO derive_order_flow_events (
              id, source_endpoint, external_event_id, event_kind,
              execution_type, leg_structure, option_mix,
              trade_ts_ms, observed_at_ms, currency, instrument_type,
              side, side_source, amount, price, premium_usd,
              order_type, time_in_force, rfq_id, quote_id, tx_hash,
              tx_status, subaccount_id, wallet
            ) VALUES (?, 'public/get_trade_history', ?, 'rfq_trade',
              'RFQ', ?, 'PUT',
              1783065457350, 1783065458000, 'HYPE', 'option',
              'unknown', 'taker_direction', ?, NULL, ?,
              NULL, NULL, 'rfq-1', 'quote-1', '0xhash',
              'settled', '58254', '0xabc'
            )
            """,
            [
                ('old-event-1', 'trade-1:58254', 'SINGLE_LEG', 2, 10),
                ('old-event-2', 'trade-2:58254', 'SINGLE_LEG', 2, 6),
                ('grouped-event', 'quote:quote-1:58254', 'MULTI_LEG', 4, 16),
            ],
        )
        self.conn.executemany(
            """
            INSERT INTO derive_order_flow_legs (
              id, event_id, leg_index, instrument_name, option_type,
              expiry, strike, side, amount, price, premium_usd
            ) VALUES (?, ?, ?, ?, 'put', '2026-07-31', ?, ?, 2, ?, ?)
            """,
            [
                ('old-leg-1', 'old-event-1', 0, 'HYPE-20260731-52-P', 52, 'buy', 5, 10),
                ('old-leg-2', 'old-event-2', 0, 'HYPE-20260731-45-P', 45, 'sell', 3, 6),
                ('group-leg-1', 'grouped-event', 0, 'HYPE-20260731-52-P', 52, 'buy', 5, 10),
                ('group-leg-2', 'grouped-event', 1, 'HYPE-20260731-45-P', 45, 'sell', 3, 6),
            ],
        )
        self.conn.commit()

        rows = get_order_flow_events(self.conn, execution_type='RFQ', limit=20)

        self.assertEqual([row['externalEventId'] for row in rows], ['quote:quote-1:58254'])
        self.assertEqual(rows[0]['legStructure'], 'MULTI_LEG')
        self.assertEqual(len(rows[0]['legs']), 2)

    def test_get_order_flow_events_returns_filtered_events_with_legs(self) -> None:
        self.conn.execute(
            """
            INSERT INTO derive_order_flow_events (
              id, source_endpoint, external_event_id, event_kind,
              execution_type, leg_structure, option_mix,
              trade_ts_ms, observed_at_ms, currency, instrument_type,
              side, side_source, amount, price, premium_usd,
              order_type, time_in_force, rfq_id, quote_id, tx_hash,
              tx_status, subaccount_id, wallet
            ) VALUES (
              'event-1', 'private/order', 'order-1', 'order',
              'ORDERBOOK_ORDER', 'SINGLE_LEG', 'CALL',
              1782592800000, 1782592801000, 'HYPE', 'option',
              'buy', 'official_direction', 1250, 2.4, 3000,
              'limit', 'post_only', NULL, NULL, NULL,
              NULL, 'sub-1', '0xabc'
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO derive_order_flow_legs (
              id, event_id, leg_index, instrument_name, option_type,
              expiry, strike, side, amount, price, premium_usd
            ) VALUES (
              'leg-1', 'event-1', 0, 'HYPE-20260703-75-C', 'call',
              '2026-07-03', 75, 'buy', 1250, 2.4, 3000
            )
            """
        )
        self.conn.commit()

        rows = get_order_flow_events(
            self.conn,
            execution_type="ORDERBOOK_ORDER",
            option_mix="CALL",
            limit=20,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "event-1")
        self.assertEqual(rows[0]["executionType"], "ORDERBOOK_ORDER")
        self.assertEqual(rows[0]["legStructure"], "SINGLE_LEG")
        self.assertEqual(rows[0]["optionMix"], "CALL")
        self.assertEqual(rows[0]["wallet"], "0xabc")
        self.assertEqual(rows[0]["legs"][0]["instrumentName"], "HYPE-20260703-75-C")

    def test_get_order_flow_events_filters_by_wallet_and_subaccount(self) -> None:
        self.conn.executemany(
            """
            INSERT INTO derive_order_flow_events (
              id, source_endpoint, external_event_id, event_kind,
              execution_type, leg_structure, option_mix,
              trade_ts_ms, observed_at_ms, currency, instrument_type,
              side, side_source, amount, price, premium_usd,
              order_type, time_in_force, rfq_id, quote_id, tx_hash,
              tx_status, subaccount_id, wallet
            ) VALUES (
              ?, 'public/get_trade_history', ?, 'rfq_trade',
              'RFQ', 'SINGLE_LEG', 'CALL',
              1782592800000, 1782592801000, 'HYPE', 'option',
              'buy', 'taker_direction', 10, 2.4, 24,
              NULL, NULL, NULL, NULL, NULL,
              'settled', ?, ?
            )
            """,
            [
                ("event-1", "trade-1", "65330", "0x7148eFBf570AdDACccc731084b74F321b1e09356"),
                ("event-2", "trade-2", "65282", "0x7148efbf570addacccc731084b74f321b1e09356"),
                ("event-3", "trade-3", "1", "0xother"),
            ],
        )
        self.conn.executemany(
            """
            INSERT INTO derive_order_flow_legs (
              id, event_id, leg_index, instrument_name, option_type,
              expiry, strike, side, amount, price, premium_usd
            ) VALUES (?, ?, 0, 'HYPE-20260703-75-C', 'call',
              '2026-07-03', 75, 'buy', 10, 2.4, 24)
            """,
            [
                ("leg-1", "event-1"),
                ("leg-2", "event-2"),
                ("leg-3", "event-3"),
            ],
        )
        self.conn.commit()

        rows = get_order_flow_events(
            self.conn,
            wallet="0x7148EFBF570ADDACCCC731084B74F321B1E09356",
            subaccount_id="65330",
            limit=20,
        )

        self.assertEqual([row["id"] for row in rows], ["event-1"])


if __name__ == "__main__":
    unittest.main()
