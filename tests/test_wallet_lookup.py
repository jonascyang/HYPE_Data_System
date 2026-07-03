from __future__ import annotations

import unittest

from hype_options.wallet_lookup import (
    DERIVE_TX_EXPLORER_BASE_URL,
    normalize_wallet_lookup_payload,
    parse_wallet_lookup_rsc,
)


class WalletLookupTest(unittest.TestCase):
    def test_parses_nested_rsc_props_and_preserves_amount_adjusted_greeks(self) -> None:
        rsc_payload = """
0:["$","div",null,{"children":"ignore"}]
1:{"props":{"wallet":"0x1111111111111111111111111111111111111111","scwOwner":"0x2222222222222222222222222222222222222222","ensName":"jonas.eth","trades":[{"tx_hash":"0xabc","instrument_name":"HYPE-20260731-100-C"}],"subaccounts":[{"subaccount_id":42,"positions":[{"instrument_name":"HYPE-20260731-100-C","amount":"5","delta":"1.25","gamma":"0.02","vega":"3.5","theta":"-0.7"}]}],"subaccountDeposits":[{"subaccount_id":42,"currency":"HYPE","amount":"10"}],"currencies":[{"currency":"HYPE"}]}}
"""

        props = parse_wallet_lookup_rsc(rsc_payload)
        result = normalize_wallet_lookup_payload(
            props,
            input_address="0x1111111111111111111111111111111111111111",
        )

        self.assertEqual(result["wallet"], "0x1111111111111111111111111111111111111111")
        self.assertEqual(result["scwOwner"], "0x2222222222222222222222222222222222222222")
        self.assertEqual(result["ensName"], "jonas.eth")
        self.assertEqual(len(result["positions"]), 1)
        position = result["positions"][0]
        self.assertEqual(position["instrumentName"], "HYPE-20260731-100-C")
        self.assertEqual(position["delta"], 1.25)
        self.assertEqual(position["gamma"], 0.02)
        self.assertEqual(position["vega"], 3.5)
        self.assertEqual(position["theta"], -0.7)
        self.assertEqual(position["amount"], 5.0)
        self.assertEqual(position["expiry"], "20260731")
        self.assertEqual(position["strike"], 100.0)
        self.assertEqual(position["optionType"], "call")
        self.assertEqual(position["txHash"], "0xabc")
        self.assertEqual(
            position["txExplorerUrl"],
            f"{DERIVE_TX_EXPLORER_BASE_URL}/0xabc",
        )
        self.assertEqual(
            result["trades"][0]["txExplorerUrl"],
            f"{DERIVE_TX_EXPLORER_BASE_URL}/0xabc",
        )

    def test_raises_for_rsc_without_wallet_props(self) -> None:
        with self.assertRaises(ValueError):
            parse_wallet_lookup_rsc('0:{"props":{"wallet":"0xabc"}}')

    def test_normalizes_trade_and_position_value_fields(self) -> None:
        result = normalize_wallet_lookup_payload(
            {
                "wallet": "0x1111111111111111111111111111111111111111",
                "scwOwner": "0x2222222222222222222222222222222222222222",
                "ensName": None,
                "trades": [
                    {
                        "instrument_name": "BTC-20260731-100000-C",
                        "direction": "sell",
                        "size": "2.5",
                        "premium": "1250.5",
                        "timestamp": 1785456000000,
                        "tx_hash": "0xdef",
                    }
                ],
                "subaccounts": [
                    {
                        "subaccount_id": 42,
                        "positions": [
                            {
                                "instrument_name": "BTC-20260731-100000-C",
                                "amount": "-2.5",
                                "mark_price": "500.2",
                                "premium": "1250.5",
                                "unrealized_pnl": "-12.5",
                            }
                        ],
                    }
                ],
                "subaccountDeposits": [],
                "currencies": [],
            },
            input_address="0x1111111111111111111111111111111111111111",
        )

        trade = result["trades"][0]
        self.assertEqual(trade["side"], "sell")
        self.assertEqual(trade["amount"], 2.5)
        self.assertEqual(trade["premiumUsd"], 1250.5)
        self.assertEqual(trade["timestampMs"], 1785456000000)

        position = result["positions"][0]
        self.assertEqual(position["side"], "short")
        self.assertEqual(position["pnl"], -12.5)
        self.assertEqual(position["premiumUsd"], 1250.5)
        self.assertEqual(position["underlying"], "BTC")

    def test_normalizes_derive_trade_amount_price_and_option_fields(self) -> None:
        result = normalize_wallet_lookup_payload(
            {
                "wallet": "0x1111111111111111111111111111111111111111",
                "scwOwner": "0x2222222222222222222222222222222222222222",
                "ensName": None,
                "trades": [
                    {
                        "instrument_name": "HYPE-20260925-42-C",
                        "direction": "sell",
                        "trade_amount": "12405",
                        "trade_price": "28.18",
                        "mark_price": "28.184127",
                        "timestamp": 1783074477419,
                        "tx_hash": "0xabc",
                    },
                    {
                        "instrument_name": "HYPE-PERP",
                        "direction": "buy",
                        "trade_amount": "12000",
                        "trade_price": "68.2",
                        "timestamp": 1783074414358,
                        "tx_hash": "0xdef",
                    },
                ],
                "subaccounts": [
                    {
                        "subaccount_id": 42,
                        "positions": [
                            {
                                "instrument_name": "HYPE-PERP",
                                "instrument_type": "perp",
                                "amount": "12000",
                                "mark_price": "68.2",
                                "unrealized_pnl": "12.5",
                            }
                        ],
                    }
                ],
                "subaccountDeposits": [],
                "currencies": [],
            },
            input_address="0x1111111111111111111111111111111111111111",
        )

        option_trade = result["trades"][0]
        self.assertEqual(option_trade["amount"], 12405.0)
        self.assertEqual(option_trade["price"], 28.18)
        self.assertEqual(option_trade["premiumUsd"], 349572.9)
        self.assertEqual(option_trade["optionType"], "call")
        self.assertEqual(option_trade["expiry"], "20260925")
        self.assertEqual(option_trade["strike"], 42.0)
        self.assertEqual(option_trade["instrumentType"], "option")

        perp_trade = result["trades"][1]
        self.assertEqual(perp_trade["instrumentType"], "perp")
        self.assertEqual(perp_trade["amount"], 12000.0)
        self.assertEqual(perp_trade["premiumUsd"], 818400.0)

        position = result["positions"][0]
        self.assertEqual(position["instrumentType"], "perp")
        self.assertEqual(position["side"], "long")

    def test_normalizes_decimal_strike_with_underscore_in_wallet_positions(self) -> None:
        result = normalize_wallet_lookup_payload(
            {
                "wallet": "0x1111111111111111111111111111111111111111",
                "scwOwner": "0x2222222222222222222222222222222222222222",
                "ensName": None,
                "trades": [
                    {
                        "instrument_name": "HYPE-20260925-42_5-C",
                        "direction": "buy",
                        "trade_amount": "10",
                        "trade_price": "2.5",
                    }
                ],
                "subaccounts": [
                    {
                        "subaccount_id": 42,
                        "positions": [
                            {
                                "instrument_name": "HYPE-20260925-42_5-C",
                                "amount": "10",
                                "mark_price": "2.5",
                            }
                        ],
                    }
                ],
                "subaccountDeposits": [],
                "currencies": [],
            },
            input_address="0x1111111111111111111111111111111111111111",
        )

        trade = result["trades"][0]
        self.assertEqual(trade["instrumentType"], "option")
        self.assertEqual(trade["optionType"], "call")
        self.assertEqual(trade["expiry"], "20260925")
        self.assertEqual(trade["strike"], 42.5)

        position = result["positions"][0]
        self.assertEqual(position["instrumentType"], "option")
        self.assertEqual(position["optionType"], "call")
        self.assertEqual(position["expiry"], "20260925")
        self.assertEqual(position["strike"], 42.5)


if __name__ == "__main__":
    unittest.main()
