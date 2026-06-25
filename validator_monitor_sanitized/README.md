# Validator Delegation Monitor

This directory contains a lightweight HYPE validator delegation monitor.

The monitor fetches delegation events for one Hyperliquid validator from Hypurrscan, normalizes delegate and undelegate rows, deduplicates events locally, and writes CSV, XLSX, and summary JSON outputs.

## File

| File | Role |
| --- | --- |
| `monitor_validator_delegations.py` | Fetches validator delegation events, normalizes delegate / undelegate amounts, deduplicates events, and writes CSV, XLSX, and summary JSON outputs |

## Run

```bash
python validator_monitor_sanitized/monitor_validator_delegations.py \
  --validator 0xd6a72f04b9868d5d6050376d5d7b729f47305cec \
  --output-dir output/data
```

## Event Identity

The monitor deduplicates events with:

```text
event_id = hash + ":" + user + ":" + time_ms + ":" + nonce
```

## Amount Convention

Delegations are stored as positive HYPE amounts. Undelegations are stored as negative HYPE amounts in `signed_amount_hype`.
