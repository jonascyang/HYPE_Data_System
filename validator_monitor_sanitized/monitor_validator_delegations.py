#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


DEFAULT_VALIDATOR = "0xd6a72f04b9868d5d6050376d5d7b729f47305cec"
API_BASE = "https://api.hypurrscan.io"
HYPE_DECIMALS = 100_000_000


def utc_from_ms(value):
    if pd.isna(value):
        return ""
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def fetch_delegation_events(validator):
    url = f"{API_BASE}/delegationsByValidator/{validator}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return url, response.json()


def normalize_events(events, validator, collected_at_utc):
    df = pd.json_normalize(events)
    if df.empty:
        return pd.DataFrame()

    rename_map = {
        "time": "time_ms",
        "action.validator": "validator",
        "action.wei": "amount_wei",
        "action.isUndelegate": "is_undelegate",
        "action.type": "action_type",
        "action.signatureChainId": "signature_chain_id",
        "action.hyperliquidChain": "hyperliquid_chain",
        "action.nonce": "nonce",
    }
    df = df.rename(columns=rename_map)

    for column in [
        "time_ms",
        "user",
        "block",
        "hash",
        "error",
        "action_type",
        "signature_chain_id",
        "hyperliquid_chain",
        "validator",
        "amount_wei",
        "is_undelegate",
        "nonce",
    ]:
        if column not in df.columns:
            df[column] = pd.NA

    df["validator"] = df["validator"].fillna(validator).astype(str).str.lower()
    df["user"] = df["user"].astype(str).str.lower()
    df["amount_wei"] = pd.to_numeric(df["amount_wei"], errors="coerce")
    df["amount_hype"] = df["amount_wei"] / HYPE_DECIMALS
    df["is_undelegate"] = df["is_undelegate"].astype(bool)
    df["action"] = df["is_undelegate"].map({True: "undelegate", False: "delegate"})
    df["signed_amount_hype"] = df["amount_hype"].where(
        ~df["is_undelegate"], -df["amount_hype"]
    )
    df["time_utc"] = df["time_ms"].apply(utc_from_ms)
    df["collected_at_utc"] = collected_at_utc
    df["source"] = "hypurrscan.delegationsByValidator"
    df["event_id"] = (
        df["hash"].astype(str)
        + ":"
        + df["user"].astype(str)
        + ":"
        + df["time_ms"].astype(str)
        + ":"
        + df["nonce"].astype(str)
    )

    columns = [
        "event_id",
        "source",
        "validator",
        "time_ms",
        "time_utc",
        "block",
        "hash",
        "user",
        "action",
        "amount_hype",
        "signed_amount_hype",
        "amount_wei",
        "is_undelegate",
        "action_type",
        "signature_chain_id",
        "hyperliquid_chain",
        "nonce",
        "error",
        "collected_at_utc",
    ]
    return df[columns]


def read_csv_if_exists(path):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def seed_from_old_snapshot(path, validator):
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "time": "time_ms",
            "action.validator": "validator",
            "action.wei": "amount_wei",
            "action.isUndelegate": "is_undelegate",
            "action.type": "action_type",
            "action.signatureChainId": "signature_chain_id",
            "action.hyperliquidChain": "hyperliquid_chain",
            "action.nonce": "nonce",
        }
    )

    events = df.to_dict(orient="records")
    return normalize_events(
        [
            {
                "time": row.get("time_ms"),
                "user": row.get("user"),
                "block": row.get("block"),
                "hash": row.get("hash"),
                "error": row.get("error") if not pd.isna(row.get("error")) else None,
                "action": {
                    "type": row.get("action_type"),
                    "signatureChainId": row.get("signature_chain_id"),
                    "hyperliquidChain": row.get("hyperliquid_chain"),
                    "validator": row.get("validator"),
                    "wei": row.get("amount_wei"),
                    "isUndelegate": str(row.get("is_undelegate")).lower() == "true",
                    "nonce": row.get("nonce"),
                },
            }
            for row in events
        ],
        validator,
        "seeded_from_existing_snapshot",
    )


def write_outputs(combined, new_rows, output_dir, validator, summary):
    safe_validator = validator.lower()
    events_path = output_dir / f"validator_delegation_events_{safe_validator}.csv"
    latest_path = output_dir / f"validator_delegation_latest_new_{safe_validator}.csv"
    summary_path = output_dir / f"validator_delegation_monitor_summary_{safe_validator}.json"
    xlsx_path = output_dir / f"validator_delegation_events_{safe_validator}.xlsx"

    combined.to_csv(events_path, index=False)
    new_rows.to_csv(latest_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            combined.to_excel(writer, index=False, sheet_name="events")
            new_rows.to_excel(writer, index=False, sheet_name="new_this_run")
    except Exception as exc:
        summary["xlsx_error"] = str(exc)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        xlsx_path = None

    return events_path, latest_path, summary_path, xlsx_path


def main():
    parser = argparse.ArgumentParser(
        description="Monitor and collect Hypurrscan delegation events for one Hyperliquid validator."
    )
    parser.add_argument("--validator", default=DEFAULT_VALIDATOR)
    parser.add_argument(
        "--output-dir",
        default=Path(__file__).resolve().parents[1] / "output" / "data",
        type=Path,
    )
    args = parser.parse_args()

    validator = args.validator.lower()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    url, raw_events = fetch_delegation_events(validator)
    fetched = normalize_events(raw_events, validator, collected_at_utc)

    events_path = output_dir / f"validator_delegation_events_{validator}.csv"
    existing = read_csv_if_exists(events_path)

    old_snapshot_path = output_dir / f"hypurrscan_delegations_{validator}.csv"
    seeded = pd.DataFrame()
    if existing.empty:
        seeded = seed_from_old_snapshot(old_snapshot_path, validator)

    before = len(existing) + len(seeded)
    all_frames = [frame for frame in [existing, seeded, fetched] if not frame.empty]
    combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()

    if not combined.empty:
        combined = (
            combined.drop_duplicates(subset=["event_id"], keep="last")
            .sort_values(["time_ms", "hash"], ascending=[False, True])
            .reset_index(drop=True)
        )

    existing_ids = set()
    for frame in [existing, seeded]:
        if not frame.empty and "event_id" in frame.columns:
            existing_ids.update(frame["event_id"].astype(str))
    new_rows = fetched[~fetched["event_id"].astype(str).isin(existing_ids)].copy()
    new_rows = new_rows.sort_values(["time_ms", "hash"], ascending=[False, True])

    summary = {
        "validator": validator,
        "source_url": url,
        "collected_at_utc": collected_at_utc,
        "fetched_rows_this_run": int(len(fetched)),
        "existing_rows_before_merge": int(before),
        "new_rows_this_run": int(len(new_rows)),
        "combined_unique_rows": int(len(combined)),
        "latest_event_utc": combined["time_utc"].iloc[0] if not combined.empty else None,
        "earliest_event_utc": combined["time_utc"].iloc[-1] if not combined.empty else None,
        "coverage_note": (
            "Hypurrscan delegationsByValidator currently exposes no pagination in its OpenAPI spec; "
            "this monitor accumulates events by repeatedly fetching the latest returned page and deduping locally."
        ),
    }

    written = write_outputs(combined, new_rows, output_dir, validator, summary)

    print("validator:", validator)
    print("source:", url)
    print("fetched_rows_this_run:", len(fetched))
    print("new_rows_this_run:", len(new_rows))
    print("combined_unique_rows:", len(combined))
    print("events_csv:", written[0])
    print("new_rows_csv:", written[1])
    print("summary_json:", written[2])
    if written[3]:
        print("events_xlsx:", written[3])


if __name__ == "__main__":
    main()
