from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


OPTION_INSTRUMENT_RE = re.compile(
    r"^(?P<currency>[A-Z]+)-(?P<expiry>\d{8})-(?P<strike>[0-9._]+)-(?P<option_type>[CP])$"
)


@dataclass(frozen=True)
class OptionInstrument:
    currency: str
    expiry: str
    strike: float
    option_type: str

    @property
    def instrument_name(self) -> str:
        return format_option_instrument(
            self.currency,
            self.expiry,
            self.strike,
            self.option_type,
        )

    @property
    def option_type_name(self) -> str:
        return "call" if self.option_type == "C" else "put"


def parse_option_instrument_name(instrument_name: str | None) -> OptionInstrument | None:
    if not instrument_name:
        return None
    match = OPTION_INSTRUMENT_RE.match(str(instrument_name))
    if not match:
        return None
    strike = _float(match.group("strike").replace("_", "."))
    if strike is None:
        return None
    return OptionInstrument(
        currency=match.group("currency").upper(),
        expiry=match.group("expiry"),
        strike=strike,
        option_type=match.group("option_type").upper(),
    )


def format_option_instrument(
    currency: str,
    expiry: str,
    strike: float,
    option_type: str,
) -> str:
    normalized_expiry = normalize_expiry(expiry)
    normalized_option_type = option_type_code(option_type)
    if normalized_option_type is None:
        raise ValueError(f"Unsupported option type: {option_type}")
    return f"{str(currency).upper()}-{normalized_expiry}-{format_strike(strike)}-{normalized_option_type}"


def format_strike(strike: float) -> str:
    value = float(strike)
    text = str(int(value)) if value.is_integer() else str(value)
    return text.replace(".", "_")


def normalize_expiry(expiry: str) -> str:
    value = str(expiry).replace("-", "")
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"Invalid expiry: {expiry}")
    return value


def option_type_code(value: Any) -> str | None:
    text = str(value or "").upper()
    if text.startswith("C"):
        return "C"
    if text.startswith("P"):
        return "P"
    return None


def option_type_name(value: Any) -> str | None:
    code = option_type_code(value)
    if code == "C":
        return "call"
    if code == "P":
        return "put"
    return None


def normalize_instrument_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).lower()
    if text in {"option", "options"}:
        return "option"
    if text in {"perp", "perpetual", "perpetual_future"}:
        return "perp"
    return text


def is_option_instrument(
    instrument_name: str | None,
    explicit_type: Any = None,
) -> bool:
    instrument_type = normalize_instrument_type(explicit_type)
    if instrument_type:
        return instrument_type == "option"
    return parse_option_instrument_name(instrument_name) is not None


def is_perp_instrument(
    instrument_name: str | None,
    explicit_type: Any = None,
) -> bool:
    instrument_type = normalize_instrument_type(explicit_type)
    if instrument_type:
        return instrument_type == "perp"
    return bool(instrument_name and str(instrument_name).upper().endswith("-PERP"))


def instrument_underlying(instrument_name: str | None) -> str | None:
    if not instrument_name:
        return None
    return str(instrument_name).split("-", 1)[0]


def extract_instrument_name(value: dict[str, Any]) -> str | None:
    instrument = value.get("instrumentName") or value.get("instrument_name") or value.get("instrument")
    return str(instrument) if instrument else None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
