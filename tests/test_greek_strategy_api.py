from __future__ import annotations

import os
import unittest

try:
    from fastapi import HTTPException

    from hype_options import api
    from hype_options import market_data

    FASTAPI_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - depends on local test env
    HTTPException = Exception
    api = None
    market_data = None
    FASTAPI_AVAILABLE = False


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is not installed for this Python interpreter")
class GreekStrategyApiTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("DATABASE_URL", ":memory:")
        self._original_wallet_client = api.WalletLookupClient
        self._original_current_ticker_map = api._current_ticker_map
        self._original_derive_client = market_data.DeriveClient

    def tearDown(self) -> None:
        api.WalletLookupClient = self._original_wallet_client
        api._current_ticker_map = self._original_current_ticker_map
        market_data.DeriveClient = self._original_derive_client

    def test_wallet_endpoint_rejects_invalid_address(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            api.greek_strategy_wallet(address="not-an-address")

        self.assertEqual(raised.exception.status_code, 400)

    def test_wallet_endpoint_uses_lookup_client(self) -> None:
        class FakeWalletLookupClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def fetch_wallet(self, address: str) -> dict:
                return {"inputAddress": address, "wallet": address, "positions": []}

        api.WalletLookupClient = FakeWalletLookupClient

        result = api.greek_strategy_wallet(
            address="0x1111111111111111111111111111111111111111"
        )

        self.assertEqual(result["wallet"], "0x1111111111111111111111111111111111111111")

    def test_portfolio_endpoint_returns_totals_and_curve(self) -> None:
        instrument = "HYPE-20260731-100-C"
        result = api.greek_strategy_portfolio_greeks(
            {
                "positions": [{"instrumentName": instrument, "amount": 100, "delta": 2.0}],
                "metric": "delta",
                "tickerByInstrument": {
                    instrument: {
                        "instrumentName": instrument,
                        "optionType": "C",
                        "strike": 100,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                    }
                },
            }
        )

        self.assertEqual(result["summary"]["totalDelta"], 2.0)
        self.assertEqual(result["summary"]["positionCount"], 1)
        self.assertEqual(len(result["curve"]["points"]), 61)
        self.assertEqual(
            [row["shock"] for row in result["curve"]["scenarioRows"]],
            [-0.2, -0.1, 0.0, 0.1, 0.2],
        )

    def test_portfolio_endpoint_returns_all_metric_curves_in_one_response(self) -> None:
        instrument = "HYPE-20260731-100-C"
        result = api.greek_strategy_portfolio_greeks(
            {
                "positions": [
                    {
                        "instrumentName": instrument,
                        "amount": 100,
                        "delta": 2.0,
                        "gamma": 0.2,
                        "vega": 10.0,
                        "theta": -1.0,
                        "side": "buy",
                    }
                ],
                "metric": "delta",
                "tickerByInstrument": {
                    instrument: {
                        "instrumentName": instrument,
                        "optionType": "C",
                        "strike": 100,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 4,
                    }
                },
            }
        )

        self.assertEqual(set(result["curves"]), {"delta", "gamma", "vega", "theta"})
        self.assertEqual(result["curves"]["vega"]["metric"], "vega")
        self.assertEqual(len(result["curves"]["vega"]["points"]), 61)
        self.assertEqual(len(result["payoffCurve"]["points"]), 61)

    def test_portfolio_endpoint_ignores_non_option_positions(self) -> None:
        instrument = "HYPE-20260731-100-C"
        result = api.greek_strategy_portfolio_greeks(
            {
                "positions": [
                    {"instrumentName": instrument, "instrumentType": "option", "amount": 100, "delta": 2.0},
                    {"instrumentName": "HYPE-FUTURE", "instrumentType": "future", "amount": 927.23, "delta": 999.0},
                ],
                "metric": "delta",
                "tickerByInstrument": {
                    instrument: {
                        "instrumentName": instrument,
                        "optionType": "C",
                        "strike": 100,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                    }
                },
            }
        )

        self.assertEqual(result["summary"]["totalDelta"], 2.0)
        self.assertEqual(result["summary"]["positionCount"], 1)
        self.assertEqual(result["curve"]["unavailableInstruments"], [])

    def test_portfolio_endpoint_rejects_cross_asset_calculation(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            api.greek_strategy_portfolio_greeks(
                {
                    "positions": [
                        {"instrumentName": "HYPE-20260731-100-C", "instrumentType": "option", "delta": 2.0},
                        {"instrumentName": "BTC-PERP", "instrumentType": "perp", "delta": 1.0},
                    ],
                    "metric": "delta",
                }
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("single asset", raised.exception.detail)

    def test_portfolio_endpoint_fetches_missing_asset_tickers_for_curve(self) -> None:
        instrument = "BTC-20260731-100000-C"

        class FakeDeriveClient:
            requests: list[tuple[str, str]] = []

            def __init__(self, *, base_url: str, currency: str, timeout: float = 20.0) -> None:
                self.currency = currency

            def get_tickers(self, expiry: str) -> dict:
                self.requests.append((self.currency, expiry))
                return {
                    "result": {
                        "tickers": {
                            instrument: {
                                "I": "100000",
                                "M": "4500",
                                "option_pricing": {
                                    "f": "100000",
                                    "i": "0.62",
                                    "d": "0.5",
                                    "g": "0.00002",
                                    "v": "100",
                                    "t": "-20",
                                },
                            }
                        }
                    }
                }

        api._current_ticker_map = lambda: {
            "HYPE-20260731-100-C": {
                "instrumentName": "HYPE-20260731-100-C",
                "optionType": "C",
                "strike": 100,
                "forwardPrice": 100,
                "markIv": 0.8,
                "dteDays": 30,
            }
        }
        market_data.DeriveClient = FakeDeriveClient

        result = api.greek_strategy_portfolio_greeks(
            {
                "positions": [{"instrumentName": instrument, "delta": 2.0, "gamma": 0.1, "vega": 1.0, "theta": -0.1}],
                "metric": "delta",
            }
        )

        self.assertEqual(result["summary"]["totalDelta"], 2.0)
        self.assertEqual(len(result["curve"]["points"]), 61)
        self.assertEqual(FakeDeriveClient.requests, [("BTC", "20260731")])

    def test_options_endpoint_serializes_current_ticker_map(self) -> None:
        api._current_ticker_map = lambda: {
            "HYPE-20260731-100-C": {
                "instrumentName": "HYPE-20260731-100-C",
                "expiry": "20260731",
                "strike": 100,
                "optionType": "C",
                "markPrice": 4.2,
            }
        }

        result = api.greek_strategy_options()

        self.assertEqual(result["options"][0]["instrumentName"], "HYPE-20260731-100-C")
        self.assertEqual(result["options"][0]["markPrice"], 4.2)
        self.assertEqual(result["options"][0]["optionType"], "call")

    def test_options_endpoint_filters_expired_tickers(self) -> None:
        now_ms = int(api.time.time() * 1000)
        future_ms = now_ms + 86_400_000
        past_ms = now_ms - 86_400_000
        api._current_ticker_map = lambda: {
            "HYPE-20990101-100-C": {
                "instrumentName": "HYPE-20990101-100-C",
                "expiryTsMs": future_ms,
                "expiry": "20990101",
                "strike": 100,
                "optionType": "C",
            },
            "HYPE-20000101-100-P": {
                "instrumentName": "HYPE-20000101-100-P",
                "expiryTsMs": past_ms,
                "expiry": "20000101",
                "strike": 100,
                "optionType": "P",
            },
        }

        result = api.greek_strategy_options()

        self.assertEqual(
            [option["instrumentName"] for option in result["options"]],
            ["HYPE-20990101-100-C"],
        )

    def test_simulate_endpoint_uses_payload_ticker_map(self) -> None:
        result = api.greek_strategy_simulate(
            {
                "legs": [
                    {
                        "instrumentName": "HYPE-20260731-100-C",
                        "side": "buy",
                        "quantity": 3,
                    }
                ],
                "tickerByInstrument": {
                    "HYPE-20260731-100-C": {
                        "instrumentName": "HYPE-20260731-100-C",
                        "optionType": "C",
                        "strike": 100,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 4,
                        "delta": 0.5,
                    }
                },
                "metric": "delta",
            }
        )

        self.assertEqual(result["premium"], -12.0)
        self.assertEqual(result["greeks"]["totalDelta"], 1.5)
        self.assertEqual(result["legs"][0]["optionType"], "call")
        self.assertIsNotNone(result["curve"])

    def test_simulate_endpoint_returns_positive_premium_for_short_option(self) -> None:
        result = api.greek_strategy_simulate(
            {
                "legs": [
                    {
                        "instrumentName": "HYPE-20260731-100-C",
                        "side": "sell",
                        "quantity": 3,
                    }
                ],
                "tickerByInstrument": {
                    "HYPE-20260731-100-C": {
                        "instrumentName": "HYPE-20260731-100-C",
                        "optionType": "C",
                        "strike": 100,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 4,
                        "delta": 0.5,
                    }
                },
                "metric": "delta",
            }
        )

        self.assertEqual(result["premium"], 12.0)
        self.assertEqual(result["greeks"]["totalDelta"], -1.5)
        self.assertEqual(result["legs"][0]["premium"], 12.0)

    def test_strategy_preview_endpoint_normalizes_frontend_decimal_strike_instrument(self) -> None:
        result = api.greek_strategy_strategy_preview(
            {
                "strategy": "custom",
                "expiry": "20260731",
                "strikes": [],
                "quantity": 1,
                "legs": [
                    {
                        "instrumentName": "HYPE-20260731-100.5-C",
                        "expiry": "20260731",
                        "strike": 100.5,
                        "optionType": "call",
                        "side": "buy",
                        "quantity": 1,
                    }
                ],
                "tickerByInstrument": {
                    "HYPE-20260731-100_5-C": {
                        "instrumentName": "HYPE-20260731-100_5-C",
                        "optionType": "C",
                        "strike": 100.5,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 4,
                        "delta": 0.5,
                    }
                },
                "metric": "delta",
            }
        )

        self.assertEqual(result["premium"], -4.0)
        self.assertEqual(result["greeks"]["totalDelta"], 0.5)
        self.assertEqual(result["legs"][0]["instrumentName"], "HYPE-20260731-100_5-C")

    def test_strategy_preview_endpoint_generates_and_simulates_template(self) -> None:
        result = api.greek_strategy_strategy_preview(
            {
                "strategy": "vertical_call_spread",
                "expiry": "20260731",
                "strikes": [90, 110],
                "quantity": 2,
                "side": "buy",
                "tickerByInstrument": {
                    "HYPE-20260731-90-C": {
                        "instrumentName": "HYPE-20260731-90-C",
                        "optionType": "C",
                        "strike": 90,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 5,
                        "delta": 0.6,
                    },
                    "HYPE-20260731-110-C": {
                        "instrumentName": "HYPE-20260731-110-C",
                        "optionType": "C",
                        "strike": 110,
                        "forwardPrice": 100,
                        "markIv": 0.8,
                        "dteDays": 30,
                        "markPrice": 2,
                        "delta": 0.3,
                    },
                },
                "metric": "delta",
            }
        )

        self.assertEqual(result["premium"], -6.0)
        self.assertEqual(result["greeks"]["totalDelta"], 0.6)
        self.assertEqual(len(result["legs"]), 2)
        self.assertIsNotNone(result["curve"])
        self.assertIsNotNone(result["payoffCurve"])
        self.assertEqual(len(result["payoffCurve"]["points"]), 61)
        current = [point for point in result["payoffCurve"]["points"] if point["shock"] == 0.0][0]
        self.assertEqual(current["value"], 14.0)


if __name__ == "__main__":
    unittest.main()
