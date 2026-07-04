from __future__ import annotations

import unittest

from hype_options.portfolio_risk import (
    SINGLE_ASSET_ERROR,
    evaluate_portfolio_positions,
    evaluate_strategy_legs,
    missing_ticker_requests,
)


class PortfolioRiskTest(unittest.TestCase):
    def test_evaluates_portfolio_summary_curves_and_payoff_in_one_response(self) -> None:
        instrument = "HYPE-20260731-100-C"
        result = evaluate_portfolio_positions(
            [
                {
                    "instrumentName": instrument,
                    "instrumentType": "option",
                    "amount": 2,
                    "side": "long",
                    "delta": 1.0,
                    "gamma": 0.2,
                    "vega": 1.0,
                    "theta": -0.1,
                }
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                    "markPrice": 5,
                }
            },
            "delta",
        )

        self.assertEqual(result["summary"]["totalDelta"], 1.0)
        self.assertEqual(result["summary"]["positionCount"], 1)
        self.assertEqual(set(result["curves"]), {"delta", "gamma", "vega", "theta"})
        self.assertEqual(len(result["curve"]["points"]), 101)
        self.assertEqual(len(result["payoffCurve"]["points"]), 101)

    def test_rejects_cross_asset_portfolio(self) -> None:
        with self.assertRaisesRegex(ValueError, SINGLE_ASSET_ERROR):
            evaluate_portfolio_positions(
                [
                    {"instrumentName": "HYPE-20260731-100-C", "instrumentType": "option", "delta": 1},
                    {"instrumentName": "BTC-PERP", "instrumentType": "perp", "delta": 1},
                ],
                {},
            )

    def test_missing_ticker_requests_use_option_positions_only(self) -> None:
        requests = missing_ticker_requests(
            [
                {"instrumentName": "BTC-20260731-100000-C", "instrumentType": "option"},
                {"instrumentName": "BTC-PERP", "instrumentType": "perp"},
                {"instrumentName": "HYPE-FUTURE", "instrumentType": "future"},
            ],
            {
                "HYPE-20260731-100-C": {
                    "forwardPrice": 100,
                    "strike": 100,
                    "markIv": 0.8,
                }
            },
        )

        self.assertEqual(requests, {("BTC", "20260731")})

    def test_strategy_short_option_returns_positive_premium_and_prefetched_curves(self) -> None:
        instrument = "HYPE-20260731-100-C"
        result = evaluate_strategy_legs(
            [
                {
                    "instrumentName": instrument,
                    "side": "sell",
                    "quantity": 3,
                }
            ],
            {
                instrument: {
                    "instrumentName": instrument,
                    "optionType": "C",
                    "strike": 100,
                    "forwardPrice": 100,
                    "markIv": 0.8,
                    "dteDays": 30,
                    "markPrice": 4,
                    "delta": 0.5,
                    "gamma": 0.02,
                    "vega": 0.3,
                    "theta": -0.1,
                }
            },
            "delta",
        )

        self.assertEqual(result["premium"], 12.0)
        self.assertEqual(result["greeks"]["totalDelta"], -1.5)
        self.assertEqual(result["legs"][0]["optionType"], "call")
        self.assertEqual(set(result["curves"]), {"delta", "gamma", "vega", "theta"})
        self.assertEqual(len(result["payoffCurve"]["points"]), 101)


if __name__ == "__main__":
    unittest.main()
