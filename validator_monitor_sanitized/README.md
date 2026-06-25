# Validator Delegation Monitor

This directory contains a sanitized review copy of the HYPE validator delegation monitor.

Source file:

```text
validator_monitor_sanitized/monitor_validator_delegations.py
```

## File

| File | Role |
| --- | --- |
| `monitor_validator_delegations.py` | Fetches validator delegation events, normalizes delegate / undelegate amounts, deduplicates events, and writes CSV, XLSX, and summary JSON outputs |

## Event Identity

The monitor deduplicates events with:

```text
event_id = hash + ":" + user + ":" + time_ms + ":" + nonce
```

## Amount Convention

Delegations are stored as positive HYPE amounts. Undelegations are stored as negative HYPE amounts in `signed_amount_hype`.
