from __future__ import annotations

import json
import re
from typing import Any

from hype_options.instruments import (
    instrument_underlying,
    is_perp_instrument,
    normalize_instrument_type,
    option_type_name,
    parse_option_instrument_name,
)


DERIVE_TX_EXPLORER_BASE_URL = "https://explorer.derive.xyz/tx"
WALLET_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
REQUIRED_WALLET_PROP_KEYS = {
    "wallet",
    "scwOwner",
    "trades",
    "subaccounts",
    "subaccountDeposits",
    "currencies",
}
POSITION_NUMERIC_FIELDS = {
    "amount",
    "delta",
    "gamma",
    "vega",
    "theta",
    "strike",
    "markPrice",
    "mark_price",
    "entryPrice",
    "entry_price",
}
INSTRUMENT_TYPE_KEYS = ("instrumentType", "instrument_type", "type")


class WalletLookupError(RuntimeError):
    pass


class WalletLookupClient:
    def __init__(self, base_url: str = "https://app.derive.xyz", timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_wallet(self, address: str) -> dict[str, Any]:
        if not is_valid_wallet_address(address):
            raise ValueError("Invalid wallet address")
        url = f"{self.base_url}/wallet/{address}?_rsc=1"
        try:
            import httpx
        except ImportError as exc:
            raise WalletLookupError("httpx is required for Derive Wallet Lookup") from exc
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers={"RSC": "1"})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WalletLookupError(f"Derive Wallet Lookup unavailable: {exc}") from exc

        props = parse_wallet_lookup_rsc(response.text)
        result = normalize_wallet_lookup_payload(props, input_address=address)
        result["source"] = {"type": "derive_wallet_lookup", "url": url}
        return result


def is_valid_wallet_address(address: str | None) -> bool:
    return bool(address and WALLET_ADDRESS_RE.match(address))


def parse_wallet_lookup_rsc(payload: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(payload):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(payload[index:])
        except json.JSONDecodeError:
            continue
        props = _find_wallet_props(value)
        if props is not None:
            return props
    raise ValueError("Wallet Lookup props object not found in RSC payload")


def normalize_wallet_lookup_payload(props: dict[str, Any], *, input_address: str) -> dict[str, Any]:
    subaccounts = _list(props.get("subaccounts"))
    trades = [_normalize_trade(trade) for trade in _list(props.get("trades"))]
    positions = _positions_from_subaccounts(subaccounts)
    positions.extend(_normalize_position(position, None) for position in _list(props.get("positions")))
    _attach_recent_trade_hashes(positions, trades)
    return {
        "inputAddress": input_address,
        "wallet": props.get("wallet"),
        "scwOwner": props.get("scwOwner"),
        "ensName": props.get("ensName"),
        "subaccounts": subaccounts,
        "subaccountDeposits": _list(props.get("subaccountDeposits")),
        "positions": positions,
        "trades": trades,
        "currencies": _list(props.get("currencies")),
        "source": {"type": "derive_wallet_lookup"},
    }


def _find_wallet_props(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if _is_wallet_props(value):
            return value
        props = value.get("props")
        if isinstance(props, dict) and _is_wallet_props(props):
            return props
        for nested in value.values():
            found = _find_wallet_props(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_wallet_props(nested)
            if found is not None:
                return found
    return None


def _is_wallet_props(value: dict[str, Any]) -> bool:
    return REQUIRED_WALLET_PROP_KEYS.issubset(value.keys())


def _positions_from_subaccounts(subaccounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    for subaccount in subaccounts:
        for key in ("positions", "openPositions", "optionPositions"):
            raw_positions = subaccount.get(key)
            if isinstance(raw_positions, list):
                positions.extend(_normalize_position(position, subaccount) for position in raw_positions)
    return positions


def _normalize_position(raw: Any, subaccount: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    position = dict(raw)
    instrument_name = _first(position, "instrumentName", "instrument_name", "instrument")
    if instrument_name is not None:
        position["instrumentName"] = str(instrument_name)
        position["underlying"] = _underlying_from_instrument(str(instrument_name))
        _fill_instrument_fields(position, str(instrument_name))
    instrument_type = _first(position, *INSTRUMENT_TYPE_KEYS)
    if instrument_type is not None:
        position["instrumentType"] = _normalize_instrument_type(instrument_type)
    subaccount_id = _first(position, "subaccountId", "subaccount_id")
    if subaccount_id is None and subaccount is not None:
        subaccount_id = _first(subaccount, "subaccountId", "subaccount_id", "id")
    if subaccount_id is not None:
        position["subaccountId"] = subaccount_id
    option_type = _first(position, "optionType", "option_type")
    if option_type is not None:
        position["optionType"] = _normalize_option_type(option_type)
    for field in POSITION_NUMERIC_FIELDS:
        value = _first(position, field)
        if value is not None:
            position[_camel_key(field)] = _to_float(value)
    premium = _first(position, "premiumUsd", "premium_usd", "premiumUSD", "premium", "optionPremium", "option_premium")
    if premium is not None:
        position["premiumUsd"] = _to_float(premium)
    pnl = _first(position, "pnl", "pnlUsd", "pnl_usd", "unrealizedPnl", "unrealized_pnl", "unrealisedPnl", "unrealised_pnl")
    if pnl is not None:
        position["pnl"] = _to_float(pnl)
    side = _normalize_position_side(_first(position, "side", "direction", "positionSide", "position_side"), position.get("amount"))
    if side is not None:
        position["side"] = side
    notional = _first(position, "notionalUsd", "notional_usd", "notional", "positionNotional", "position_notional")
    if notional is not None:
        position["notionalUsd"] = _to_float(notional)
    elif position.get("amount") is not None and position.get("strike") is not None:
        position["notionalUsd"] = abs(float(position["amount"]) * float(position["strike"]))
    return position


def _normalize_trade(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    trade = dict(raw)
    tx_hash = _first(trade, "txHash", "tx_hash")
    if tx_hash is not None:
        trade["txHash"] = tx_hash
        trade["txExplorerUrl"] = f"{DERIVE_TX_EXPLORER_BASE_URL}/{tx_hash}"
    instrument_name = _first(trade, "instrumentName", "instrument_name")
    if instrument_name is not None:
        trade["instrumentName"] = str(instrument_name)
        trade["underlying"] = _underlying_from_instrument(str(instrument_name))
        _fill_instrument_fields(trade, str(instrument_name))
    instrument_type = _first(trade, *INSTRUMENT_TYPE_KEYS)
    if instrument_type is not None:
        trade["instrumentType"] = _normalize_instrument_type(instrument_type)
    side = _normalize_trade_side(_first(trade, "side", "direction", "tradeSide", "trade_side", "orderSide", "order_side"))
    if side is not None:
        trade["side"] = side
    amount = _first(trade, "amount", "tradeAmount", "trade_amount", "size", "qty", "quantity", "contracts")
    if amount is not None:
        trade["amount"] = _to_float(amount)
    price = _first(trade, "tradePrice", "trade_price", "fillPrice", "fill_price", "price", "markPrice", "mark_price")
    if price is not None:
        trade["price"] = _to_float(price)
    premium = _first(trade, "premiumUsd", "premium_usd", "premiumUSD", "premium", "cost", "value")
    if premium is not None:
        trade["premiumUsd"] = _to_float(premium)
    elif trade.get("amount") is not None and trade.get("price") is not None:
        trade["premiumUsd"] = abs(float(trade["amount"]) * float(trade["price"]))
    timestamp = _first(trade, "timestampMs", "timestamp_ms", "tradeTsMs", "trade_ts_ms", "createdAtMs", "created_at_ms", "timestamp", "createdAt", "created_at")
    if timestamp is not None:
        trade["timestampMs"] = _to_timestamp_ms(timestamp)
    return trade


def _fill_instrument_fields(position: dict[str, Any], instrument_name: str) -> None:
    instrument = parse_option_instrument_name(instrument_name)
    if instrument is not None:
        position.setdefault("instrumentType", "option")
        position.setdefault("expiry", instrument.expiry)
        position.setdefault("strike", instrument.strike)
        position.setdefault("optionType", instrument.option_type_name)
        return
    if is_perp_instrument(instrument_name):
        position.setdefault("instrumentType", "perp")


def _normalize_option_type(value: Any) -> str:
    return option_type_name(value) or str(value)


def _normalize_instrument_type(value: Any) -> str:
    return normalize_instrument_type(value) or str(value)


def _underlying_from_instrument(instrument_name: str) -> str | None:
    return instrument_underlying(instrument_name)


def _normalize_trade_side(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).lower()
    if text in {"buy", "b", "bid", "long"}:
        return "buy"
    if text in {"sell", "s", "ask", "short"}:
        return "sell"
    return str(value)


def _normalize_position_side(value: Any, amount: Any = None) -> str | None:
    if value is not None:
        text = str(value).lower()
        if text in {"long", "buy", "b"}:
            return "long"
        if text in {"short", "sell", "s"}:
            return "short"
    numeric_amount = _to_float(amount)
    if numeric_amount is None:
        return None
    return "long" if numeric_amount >= 0 else "short"


def _attach_recent_trade_hashes(positions: list[dict[str, Any]], trades: list[dict[str, Any]]) -> None:
    tx_by_instrument: dict[str, str] = {}
    for trade in trades:
        instrument = trade.get("instrumentName")
        tx_hash = trade.get("txHash")
        if instrument and tx_hash and instrument not in tx_by_instrument:
            tx_by_instrument[str(instrument)] = str(tx_hash)
    for position in positions:
        if position.get("txHash"):
            continue
        instrument = position.get("instrumentName")
        tx_hash = tx_by_instrument.get(str(instrument)) if instrument else None
        if tx_hash:
            position["txHash"] = tx_hash
            position["txExplorerUrl"] = f"{DERIVE_TX_EXPLORER_BASE_URL}/{tx_hash}"


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source[key] not in (None, ""):
            return source[key]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_timestamp_ms(value: Any) -> int | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    if numeric < 10_000_000_000:
        numeric *= 1000
    return int(numeric)


def _camel_key(key: str) -> str:
    if "_" not in key:
        return key
    head, *tail = key.split("_")
    return head + "".join(part.capitalize() for part in tail)
