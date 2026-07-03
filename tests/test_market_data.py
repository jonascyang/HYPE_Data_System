from __future__ import annotations

import unittest

from hype_options.market_data import (
    complete_ticker_map_for_positions,
    option_choices,
    ticker_map_from_payload,
    ticker_map_from_realtime_snapshot,
    ticker_map_from_ticker_payload,
)


class MarketDataTest(unittest.TestCase):
    def test_ticker_payload_normalizes_decimal_strike_instrument_key(self) -> None:
        payload = {
            "result": {
                "tickers": {
                    "HYPE-20260731-100.5-C": {
                        "I": "99.5",
                        "M": "4.2",
                        "b": "4.1",
                        "a": "4.3",
                        "option_pricing": {
                            "f": "100",
                            "i": "0.8",
                            "d": "0.51",
                            "g": "0.02",
                            "v": "10",
                            "t": "-1",
                        },
                    }
                }
            }
        }

        ticker_map = ticker_map_from_ticker_payload(payload, "20260731")

        ticker = ticker_map["HYPE-20260731-100_5-C"]
        self.assertEqual(ticker["instrumentName"], "HYPE-20260731-100_5-C")
        self.assertEqual(ticker["strike"], 100.5)
        self.assertEqual(ticker["markPrice"], 4.2)
        self.assertEqual(ticker["forwardPrice"], 100.0)
        self.assertEqual(ticker["optionType"], "C")

    def test_realtime_snapshot_builds_canonical_ticker_map(self) -> None:
        class Snapshot:
            bootstrap = {
                "ivSmileByExpiry": {
                    "20260731": [
                        {
                            "strike": 100.5,
                            "callIv": 0.8,
                            "callDelta": 0.51,
                            "callGamma": 0.02,
                            "callVega": 10,
                            "callTheta": -1,
                            "callPremium": 4.2,
                            "putIv": None,
                        }
                    ]
                }
            }

        ticker_map = ticker_map_from_realtime_snapshot(Snapshot())

        self.assertEqual(list(ticker_map), ["HYPE-20260731-100_5-C"])
        self.assertEqual(ticker_map["HYPE-20260731-100_5-C"]["markIv"], 0.8)
        self.assertEqual(ticker_map["HYPE-20260731-100_5-C"]["markPrice"], 4.2)

    def test_complete_ticker_map_fetches_only_missing_curve_inputs(self) -> None:
        instrument = "BTC-20260731-100000-C"

        class Settings:
            derive_base_url = "https://derive.invalid"

        class FakeDeriveClient:
            requests: list[tuple[str, str, str]] = []

            def __init__(self, *, base_url: str, currency: str) -> None:
                self.base_url = base_url
                self.currency = currency

            def get_tickers(self, expiry: str) -> dict:
                self.requests.append((self.base_url, self.currency, expiry))
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

        result = complete_ticker_map_for_positions(
            [{"instrumentName": instrument, "instrumentType": "option"}],
            {},
            settings=Settings(),
            client_factory=FakeDeriveClient,
        )

        self.assertEqual(FakeDeriveClient.requests, [("https://derive.invalid", "BTC", "20260731")])
        self.assertIn(instrument, result)
        self.assertEqual(result[instrument]["markIv"], 0.62)

    def test_ticker_map_from_payload_prefers_supplied_map(self) -> None:
        supplied = {"HYPE-20260731-100-C": {"instrumentName": "HYPE-20260731-100-C"}}

        self.assertIs(
            ticker_map_from_payload({"tickerByInstrument": supplied}, lambda: {}),
            supplied,
        )

    def test_option_choices_filter_expired_tickers(self) -> None:
        ticker_map = {
            "HYPE-20990101-100-C": {
                "instrumentName": "HYPE-20990101-100-C",
                "expiry": "20990101",
                "strike": 100,
                "optionType": "C",
                "markPrice": 4.2,
            },
            "HYPE-20000101-100-P": {
                "instrumentName": "HYPE-20000101-100-P",
                "expiry": "20000101",
                "strike": 100,
                "optionType": "P",
            },
        }

        choices = option_choices(ticker_map, now_ms=1_800_000_000_000)

        self.assertEqual([choice["instrumentName"] for choice in choices], ["HYPE-20990101-100-C"])
        self.assertEqual(choices[0]["optionType"], "call")


if __name__ == "__main__":
    unittest.main()
