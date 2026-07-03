from __future__ import annotations

import unittest

from hype_options.instruments import (
    format_option_instrument,
    instrument_underlying,
    is_option_instrument,
    is_perp_instrument,
    option_type_code,
    option_type_name,
    parse_option_instrument_name,
)


class InstrumentsTest(unittest.TestCase):
    def test_parses_hype_option_with_integer_strike(self) -> None:
        instrument = parse_option_instrument_name("HYPE-20260731-100-C")

        self.assertIsNotNone(instrument)
        assert instrument is not None
        self.assertEqual(instrument.currency, "HYPE")
        self.assertEqual(instrument.expiry, "20260731")
        self.assertEqual(instrument.strike, 100.0)
        self.assertEqual(instrument.option_type, "C")
        self.assertEqual(instrument.option_type_name, "call")
        self.assertEqual(instrument.instrument_name, "HYPE-20260731-100-C")

    def test_parses_decimal_strike_with_dot_or_underscore_to_same_identity(self) -> None:
        dot = parse_option_instrument_name("HYPE-20260731-100.5-C")
        underscore = parse_option_instrument_name("HYPE-20260731-100_5-C")

        self.assertIsNotNone(dot)
        self.assertIsNotNone(underscore)
        assert dot is not None
        assert underscore is not None
        self.assertEqual(dot.strike, 100.5)
        self.assertEqual(underscore.strike, 100.5)
        self.assertEqual(dot.instrument_name, "HYPE-20260731-100_5-C")
        self.assertEqual(underscore.instrument_name, "HYPE-20260731-100_5-C")

    def test_formats_cross_asset_option_instrument(self) -> None:
        self.assertEqual(
            format_option_instrument("btc", "2026-07-31", 100000.5, "call"),
            "BTC-20260731-100000_5-C",
        )

    def test_classifies_option_and_perp(self) -> None:
        self.assertTrue(is_option_instrument("BTC-20260731-100000-P"))
        self.assertTrue(is_option_instrument(None, "options"))
        self.assertFalse(is_option_instrument("BTC-PERP"))
        self.assertTrue(is_perp_instrument("BTC-PERP"))
        self.assertTrue(is_perp_instrument(None, "perpetual_future"))
        self.assertFalse(is_perp_instrument("BTC-20260731-100000-P"))

    def test_normalizes_option_type_and_underlying(self) -> None:
        self.assertEqual(option_type_code("put"), "P")
        self.assertEqual(option_type_name("C"), "call")
        self.assertEqual(instrument_underlying("BTC-20260731-100000-P"), "BTC")
        self.assertIsNone(instrument_underlying(None))


if __name__ == "__main__":
    unittest.main()
