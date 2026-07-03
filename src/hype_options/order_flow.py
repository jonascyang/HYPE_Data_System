from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from hype_options.instruments import option_type_name, parse_option_instrument_name


ORDERBOOK_ENDPOINTS = {"private/order", "order", "private_order"}
RFQ_ENDPOINTS = {"send_rfq", "send_quote", "execute_quote", "rfq", "quote"}
PUBLIC_TRADE_HISTORY_ENDPOINT = "public/get_trade_history"
VALID_SIDES = {"buy", "sell", "unknown"}
VALID_ORDER_TYPES = {"limit", "market"}
VALID_TIME_IN_FORCE = {"gtc", "post_only", "fok", "ioc"}


@dataclass(frozen=True)
class NormalizedOrderFlowEvent:
    event: dict[str, Any]
    legs: list[dict[str, Any]]


def normalize_public_trade_history_row(
    row: dict[str, Any],
    *,
    observed_at_ms: int,
    include_maker_rows: bool = False,
) -> NormalizedOrderFlowEvent | None:
    events = normalize_public_trade_history_rows(
        [row],
        observed_at_ms=observed_at_ms,
        include_maker_rows=include_maker_rows,
    )
    return events[0] if events else None


def normalize_public_trade_history_rows(
    rows: list[dict[str, Any]],
    *,
    observed_at_ms: int,
    include_maker_rows: bool = False,
) -> list[NormalizedOrderFlowEvent]:
    grouped_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not _is_public_trade_history_row_eligible(row, include_maker_rows=include_maker_rows):
            continue
        group_key = _public_trade_history_group_key(row)
        if group_key is None:
            continue
        grouped_rows.setdefault(group_key, []).append(row)

    events: list[NormalizedOrderFlowEvent] = []
    for group_key, group_rows in grouped_rows.items():
        normalized = _normalize_public_trade_history_group(
            group_key,
            group_rows,
            observed_at_ms=observed_at_ms,
        )
        if normalized is not None:
            events.append(normalized)
    return events


def _normalize_public_trade_history_group(
    group_key: tuple[str, str, str],
    rows: list[dict[str, Any]],
    *,
    observed_at_ms: int,
) -> NormalizedOrderFlowEvent | None:
    if not rows:
        return None

    kind, external_id, participant_suffix = group_key
    first = rows[0]
    rfq_id = _first_text(rows, "rfq_id")
    quote_id = _first_text(rows, "quote_id")
    event_kind = "rfq_trade" if rfq_id or quote_id else "orderbook_trade"
    total_premium = 0.0
    has_price = False
    legs: list[dict[str, Any]] = []
    for row in rows:
        instrument_name = _nullable_text(row.get("instrument_name"))
        amount = _float(row.get("trade_amount"))
        price = _float(row.get("trade_price"))
        if not instrument_name or amount is None:
            continue
        premium_usd = abs(amount * price) if price is not None else None
        if premium_usd is not None:
            total_premium += premium_usd
            has_price = True
        legs.append(
            {
                "instrument_name": instrument_name,
                "side": row.get("direction"),
                "amount": amount,
                "price": price,
                "premium_usd": premium_usd,
            }
        )
    if not legs:
        return None

    return normalize_order_flow_event(
        {
            "source_endpoint": PUBLIC_TRADE_HISTORY_ENDPOINT,
            "external_event_id": f"{kind}:{external_id}:{participant_suffix}",
            "event_kind": event_kind,
            "trade_ts_ms": _max_int(row.get("timestamp") for row in rows),
            "side": _shared_side(rows),
            "side_source": _public_side_source(rows),
            "amount": sum(float(leg.get("amount") or 0) for leg in legs),
            "price": _float(first.get("trade_price")) if len(legs) == 1 else None,
            "premium_usd": total_premium if has_price else None,
            "rfq_id": rfq_id,
            "quote_id": quote_id,
            "tx_hash": _first_text(rows, "tx_hash"),
            "tx_status": _first_text(rows, "tx_status"),
            "subaccount_id": _first_text(rows, "subaccount_id"),
            "wallet": _first_text(rows, "wallet"),
            "currency": "HYPE",
            "instrument_type": "option",
            "legs": legs,
        },
        observed_at_ms=observed_at_ms,
    )


def _is_public_trade_history_row_eligible(row: dict[str, Any], *, include_maker_rows: bool) -> bool:
    liquidity_role = str(row.get("liquidity_role") or "").lower()
    if liquidity_role == "maker" and not include_maker_rows:
        return False

    trade_id = _nullable_text(row.get("trade_id"))
    instrument_name = _nullable_text(row.get("instrument_name"))
    amount = _float(row.get("trade_amount"))
    if not trade_id or not instrument_name or amount is None:
        return False
    return True


def _public_trade_history_group_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
    participant_suffix = _public_participant_suffix(row)
    rfq_id = _nullable_text(row.get("rfq_id"))
    quote_id = _nullable_text(row.get("quote_id"))
    trade_id = _nullable_text(row.get("trade_id"))
    if quote_id:
        return ("quote", quote_id, participant_suffix)
    if rfq_id:
        return ("rfq", rfq_id, participant_suffix)
    if trade_id:
        return ("trade", trade_id, participant_suffix)
    return None


def _public_participant_suffix(row: dict[str, Any]) -> str:
    liquidity_role = str(row.get("liquidity_role") or "").lower()
    return _nullable_text(row.get("subaccount_id")) or _nullable_text(row.get("wallet")) or liquidity_role or "unknown"


def normalize_order_flow_event(raw: dict[str, Any], *, observed_at_ms: int) -> NormalizedOrderFlowEvent | None:
    source_endpoint = str(raw.get("source_endpoint") or raw.get("sourceEndpoint") or "")
    event_kind = str(raw.get("event_kind") or raw.get("eventKind") or source_endpoint or "")
    execution_type = _execution_type(source_endpoint, event_kind)
    if execution_type is None:
        return None

    raw_legs = raw.get("legs")
    if not raw_legs:
        instrument_name = raw.get("instrument_name") or raw.get("instrumentName")
        if not instrument_name:
            return None
        raw_legs = [
            {
                "instrument_name": instrument_name,
                "side": raw.get("side"),
                "amount": raw.get("amount"),
                "price": raw.get("price"),
                "premium_usd": raw.get("premium_usd") or raw.get("premiumUsd"),
            }
        ]

    legs = _normalize_legs(raw_legs)
    if not legs:
        return None

    leg_structure = "SINGLE_LEG" if len(legs) == 1 else "MULTI_LEG"
    option_mix = _option_mix(legs)
    external_event_id = str(raw.get("external_event_id") or raw.get("externalEventId") or raw.get("id") or "")
    if not external_event_id:
        return None

    side = _side(raw.get("side"))
    premium_usd = _float(raw.get("premium_usd") or raw.get("premiumUsd"))
    if premium_usd is None:
        premium_usd = sum(float(leg.get("premium_usd") or 0) for leg in legs)

    amount = _float(raw.get("amount"))
    if amount is None:
        amount = sum(float(leg.get("amount") or 0) for leg in legs)

    order_type = _nullable_choice(raw.get("order_type") or raw.get("orderType"), VALID_ORDER_TYPES)
    time_in_force = _nullable_choice(raw.get("time_in_force") or raw.get("timeInForce"), VALID_TIME_IN_FORCE)
    if execution_type == "RFQ":
        order_type = None
        time_in_force = None

    event = {
        "id": _stable_id(source_endpoint, external_event_id),
        "source_endpoint": source_endpoint,
        "external_event_id": external_event_id,
        "event_kind": event_kind,
        "execution_type": execution_type,
        "leg_structure": leg_structure,
        "option_mix": option_mix,
        "trade_ts_ms": _int(raw.get("trade_ts_ms") or raw.get("tradeTsMs")),
        "observed_at_ms": observed_at_ms,
        "currency": str(raw.get("currency") or "HYPE"),
        "instrument_type": str(raw.get("instrument_type") or raw.get("instrumentType") or "option"),
        "side": side,
        "side_source": str(raw.get("side_source") or raw.get("sideSource") or "unavailable"),
        "amount": amount,
        "price": _float(raw.get("price")),
        "premium_usd": premium_usd,
        "order_type": order_type,
        "time_in_force": time_in_force,
        "rfq_id": _nullable_text(raw.get("rfq_id") or raw.get("rfqId")),
        "quote_id": _nullable_text(raw.get("quote_id") or raw.get("quoteId")),
        "tx_hash": _nullable_text(raw.get("tx_hash") or raw.get("txHash")),
        "tx_status": _nullable_text(raw.get("tx_status") or raw.get("txStatus")),
        "subaccount_id": _nullable_text(raw.get("subaccount_id") or raw.get("subaccountId")),
        "wallet": _nullable_text(raw.get("wallet")),
    }

    event_id = event["id"]
    return NormalizedOrderFlowEvent(
        event=event,
        legs=[
            {
                "id": _stable_id(event_id, str(leg["leg_index"])),
                "event_id": event_id,
                **leg,
            }
            for leg in legs
        ],
    )


def insert_order_flow_event(conn, normalized: NormalizedOrderFlowEvent) -> None:
    event_columns = [
        "id",
        "source_endpoint",
        "external_event_id",
        "event_kind",
        "execution_type",
        "leg_structure",
        "option_mix",
        "trade_ts_ms",
        "observed_at_ms",
        "currency",
        "instrument_type",
        "side",
        "side_source",
        "amount",
        "price",
        "premium_usd",
        "order_type",
        "time_in_force",
        "rfq_id",
        "quote_id",
        "tx_hash",
        "tx_status",
        "subaccount_id",
        "wallet",
    ]
    leg_columns = [
        "id",
        "event_id",
        "leg_index",
        "instrument_name",
        "option_type",
        "expiry",
        "strike",
        "side",
        "amount",
        "price",
        "premium_usd",
    ]
    conn.execute(
        f"""
        INSERT OR REPLACE INTO derive_order_flow_events ({", ".join(event_columns)})
        VALUES ({", ".join("?" for _ in event_columns)})
        """,
        tuple(normalized.event[column] for column in event_columns),
    )
    conn.execute("DELETE FROM derive_order_flow_legs WHERE event_id = ?", (normalized.event["id"],))
    conn.executemany(
        f"""
        INSERT OR REPLACE INTO derive_order_flow_legs ({", ".join(leg_columns)})
        VALUES ({", ".join("?" for _ in leg_columns)})
        """,
        [tuple(leg[column] for column in leg_columns) for leg in normalized.legs],
    )
    conn.commit()


def get_order_flow_events(
    conn,
    *,
    execution_type: str | None = None,
    leg_structure: str | None = None,
    option_mix: str | None = None,
    side: str | None = None,
    order_type: str | None = None,
    time_in_force: str | None = None,
    min_amount: float | None = None,
    min_premium_usd: float | None = None,
    wallet: str | None = None,
    subaccount_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("execution_type", execution_type),
        ("leg_structure", leg_structure),
        ("option_mix", option_mix),
        ("side", side),
        ("order_type", order_type),
        ("time_in_force", time_in_force),
    ):
        if value:
            clauses.append(f"event.{column} = ?")
            params.append(value)
    if min_amount is not None:
        clauses.append("COALESCE(event.amount, 0) >= ?")
        params.append(float(min_amount))
    if min_premium_usd is not None:
        clauses.append("COALESCE(event.premium_usd, 0) >= ?")
        params.append(float(min_premium_usd))
    if wallet:
        clauses.append("LOWER(COALESCE(event.wallet, '')) = LOWER(?)")
        params.append(wallet.strip())
    if subaccount_id:
        clauses.append("event.subaccount_id = ?")
        params.append(subaccount_id.strip())
    clauses.append(
        """
        NOT (
          event.source_endpoint = 'public/get_trade_history'
          AND event.execution_type = 'RFQ'
          AND event.quote_id IS NOT NULL
          AND event.external_event_id NOT LIKE 'quote:%'
          AND EXISTS (
            SELECT 1
            FROM derive_order_flow_events AS grouped_event
            WHERE grouped_event.source_endpoint = event.source_endpoint
              AND grouped_event.execution_type = event.execution_type
              AND grouped_event.quote_id = event.quote_id
              AND COALESCE(grouped_event.subaccount_id, '') = COALESCE(event.subaccount_id, '')
              AND COALESCE(grouped_event.wallet, '') = COALESCE(event.wallet, '')
              AND grouped_event.external_event_id LIKE 'quote:%'
          )
        )
        """
    )

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = _rows_as_dicts(
        conn.execute(
            f"""
            SELECT
              id,
              source_endpoint,
              external_event_id,
              event_kind,
              execution_type,
              leg_structure,
              option_mix,
              trade_ts_ms,
              observed_at_ms,
              currency,
              side,
              side_source,
              amount,
              price,
              premium_usd,
              order_type,
              time_in_force,
              rfq_id,
              quote_id,
              tx_hash,
              tx_status,
              subaccount_id,
              wallet
            FROM derive_order_flow_events AS event
            {where_sql}
            ORDER BY COALESCE(event.trade_ts_ms, event.observed_at_ms) DESC, event.observed_at_ms DESC
            LIMIT ?
            """,
            (*params, max(1, min(int(limit), 500))),
        )
    )
    if not rows:
        return []

    event_ids = [row["id"] for row in rows]
    placeholders = ", ".join("?" for _ in event_ids)
    leg_rows = _rows_as_dicts(
        conn.execute(
            f"""
            SELECT
              event_id,
              leg_index,
              instrument_name,
              option_type,
              expiry,
              strike,
              side,
              amount,
              price,
              premium_usd
            FROM derive_order_flow_legs
            WHERE event_id IN ({placeholders})
            ORDER BY event_id, leg_index
            """,
            tuple(event_ids),
        )
    )
    legs_by_event: dict[str, list[dict[str, Any]]] = {}
    for leg in leg_rows:
        legs_by_event.setdefault(leg["event_id"], []).append(_serialize_leg(leg))

    return [_serialize_event(row, legs_by_event.get(row["id"], [])) for row in rows]


def _first_text(rows: list[dict[str, Any]], key: str) -> str | None:
    for row in rows:
        value = _nullable_text(row.get(key))
        if value is not None:
            return value
    return None


def _max_int(values: Any) -> int | None:
    parsed = [_int(value) for value in values]
    valid = [value for value in parsed if value is not None]
    return max(valid) if valid else None


def _shared_side(rows: list[dict[str, Any]]) -> str:
    sides = {_side(row.get("direction")) for row in rows}
    sides.discard("unknown")
    return sides.pop() if len(sides) == 1 else "unknown"


def _public_side_source(rows: list[dict[str, Any]]) -> str:
    roles = {str(row.get("liquidity_role") or "").lower() for row in rows}
    return "taker_direction" if roles == {"taker"} else "participant_direction"


def _execution_type(source_endpoint: str, event_kind: str) -> str | None:
    source = source_endpoint.lower()
    kind = event_kind.lower()
    if source == PUBLIC_TRADE_HISTORY_ENDPOINT:
        if kind == "rfq_trade":
            return "RFQ"
        if kind == "orderbook_trade":
            return "ORDERBOOK_ORDER"
    if source in ORDERBOOK_ENDPOINTS or kind in ORDERBOOK_ENDPOINTS:
        return "ORDERBOOK_ORDER"
    if source in RFQ_ENDPOINTS or kind in RFQ_ENDPOINTS:
        return "RFQ"
    return None


def _normalize_legs(raw_legs: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_legs, list):
        return []
    legs: list[dict[str, Any]] = []
    for index, raw_leg in enumerate(raw_legs):
        if not isinstance(raw_leg, dict):
            return []
        instrument_name = str(raw_leg.get("instrument_name") or raw_leg.get("instrumentName") or "")
        instrument = _parse_instrument_name(instrument_name)
        amount = _float(raw_leg.get("amount"))
        if instrument is None or amount is None:
            return []
        legs.append(
            {
                "leg_index": index,
                "instrument_name": instrument_name,
                "option_type": instrument["option_type"],
                "expiry": instrument["expiry"],
                "strike": instrument["strike"],
                "side": _side(raw_leg.get("side")),
                "amount": amount,
                "price": _float(raw_leg.get("price")),
                "premium_usd": _float(raw_leg.get("premium_usd") or raw_leg.get("premiumUsd")),
            }
        )
    return legs


def _parse_instrument_name(instrument_name: str) -> dict[str, Any] | None:
    instrument = parse_option_instrument_name(instrument_name)
    if instrument is None:
        return None
    expiry = instrument.expiry
    return {
        "option_type": option_type_name(instrument.option_type),
        "expiry": f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}",
        "strike": instrument.strike,
    }


def _option_mix(legs: list[dict[str, Any]]) -> str:
    option_types = {leg["option_type"] for leg in legs}
    if option_types == {"call"}:
        return "CALL"
    if option_types == {"put"}:
        return "PUT"
    return "BOTH"


def _serialize_event(row: dict[str, Any], legs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sourceEndpoint": row["source_endpoint"],
        "externalEventId": row["external_event_id"],
        "eventKind": row["event_kind"],
        "executionType": row["execution_type"],
        "legStructure": row["leg_structure"],
        "optionMix": row["option_mix"],
        "tradeTsMs": row["trade_ts_ms"],
        "observedAtMs": row["observed_at_ms"],
        "currency": row["currency"],
        "side": row["side"],
        "sideSource": row["side_source"],
        "amount": row["amount"],
        "price": row["price"],
        "premiumUsd": row["premium_usd"],
        "orderType": row["order_type"],
        "timeInForce": row["time_in_force"],
        "rfqId": row["rfq_id"],
        "quoteId": row["quote_id"],
        "txHash": row["tx_hash"],
        "txStatus": row["tx_status"],
        "subaccountId": row["subaccount_id"],
        "wallet": row.get("wallet"),
        "legs": legs,
    }


def _serialize_leg(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "legIndex": row["leg_index"],
        "instrumentName": row["instrument_name"],
        "optionType": row["option_type"],
        "expiry": row["expiry"],
        "strike": row["strike"],
        "side": row["side"],
        "amount": row["amount"],
        "price": row["price"],
        "premiumUsd": row["premium_usd"],
    }


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _stable_id(*parts: str) -> str:
    value = "|".join(parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _side(value: Any) -> str:
    side = str(value or "unknown").lower()
    return side if side in VALID_SIDES else "unknown"


def _nullable_choice(value: Any, valid: set[str]) -> str | None:
    if value is None:
        return None
    text = str(value).lower()
    return text if text in valid else None


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
