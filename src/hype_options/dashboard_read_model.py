from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any


MS_PER_DAY = 86_400_000
DEFAULT_VOL_TENORS = ("1W", "1M", "3M", "6M")
VERSIONED_PANELS = (
    "snapshot",
    "summary",
    "expiries",
    "atmTerm",
    "skewFly",
    "oiByExpiry",
    "ivSmile",
    "gexByStrike",
    "gexByExpiry",
    "oiByStrike",
    "volRegime",
)


@dataclass(frozen=True)
class RuntimeDashboardSnapshot:
    snapshot_id: int
    bootstrap: dict[str, Any]
    iv_smile_by_expiry: dict[str, list[dict[str, Any]]]
    oi_by_strike: list[dict[str, Any]]
    vol_regime_history: list[dict[str, Any]]
    current_atm_terms: list[dict[str, Any]]
    lookback_days: int

    def bootstrap_payload(
        self,
        *,
        selected_expiry: str | None = None,
        lookback_days: int | None = None,
    ) -> dict[str, Any]:
        payload = copy.deepcopy(self.bootstrap)
        expiry = selected_expiry or payload.get("selectedExpiry")
        effective_lookback_days = lookback_days or self.lookback_days
        if expiry:
            payload["selectedExpiry"] = expiry
            payload["ivSmile"] = self.iv_smile_by_expiry.get(expiry, [])
        if lookback_days is not None and lookback_days != self.lookback_days:
            vol_regime = vol_regime_from_terms(
                current_terms=self.current_atm_terms,
                history_rows=self.vol_regime_history,
                tenor=str(payload.get("summary", {}).get("volRegimeTenor") or "1M"),
                lookback_days=lookback_days,
                latest_ts_ms=self.snapshot_id,
            )
            payload["volRegime"] = vol_regime
            payload["summary"]["ivRank"] = vol_regime.get("ivRank")
            payload["summary"]["ivPercentile"] = vol_regime.get("ivPercentile")
            payload["summary"]["volRegimeLookbackDays"] = vol_regime.get("lookbackDays")
        payload["volRegimeByTenor"] = self.vol_regime_by_tenor(lookback_days=effective_lookback_days)
        payload["snapshotVersion"] = str(self.snapshot_id)
        payload["panelVersions"] = self.panel_versions(
            selected_expiry=expiry,
            lookback_days=effective_lookback_days,
        )
        return payload

    def panel_payload(self, panel: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        if panel == "snapshot":
            return self.bootstrap["snapshot"]
        if panel in {"summary", "atmTerm", "skewFly", "vrpHistory", "expiries", "oiByExpiry"}:
            return self.bootstrap.get(panel)
        if panel == "ivSmile":
            expiry = str(params.get("expiry") or self.bootstrap.get("selectedExpiry") or "")
            return self.iv_smile_by_expiry.get(expiry, [])
        if panel == "gexByStrike":
            return self.bootstrap.get("gexByStrike", [])
        if panel == "gexByExpiry":
            return self.bootstrap.get("gexByExpiry", [])
        if panel == "oiByStrike":
            return self.oi_by_strike
        if panel == "volRegime":
            return vol_regime_from_terms(
                current_terms=self.current_atm_terms,
                history_rows=self.vol_regime_history,
                tenor=str(params.get("tenor") or "1M"),
                lookback_days=int(params.get("lookbackDays") or self.lookback_days),
                latest_ts_ms=self.snapshot_id,
            )
        raise ValueError(f"Unsupported panel: {panel}")

    def vol_regime_by_tenor(self, *, lookback_days: int | None = None) -> dict[str, dict[str, Any]]:
        return {
            tenor: vol_regime_from_terms(
                current_terms=self.current_atm_terms,
                history_rows=self.vol_regime_history,
                tenor=tenor,
                lookback_days=lookback_days or self.lookback_days,
                latest_ts_ms=self.snapshot_id,
            )
            for tenor in DEFAULT_VOL_TENORS
        }

    def panel_versions(
        self,
        *,
        selected_expiry: str | None = None,
        lookback_days: int | None = None,
    ) -> dict[str, str]:
        versions: dict[str, str] = {}
        for panel in VERSIONED_PANELS:
            params: dict[str, Any] = {}
            if panel == "ivSmile":
                params["expiry"] = selected_expiry or self.bootstrap.get("selectedExpiry")
            elif panel == "volRegime":
                params["tenor"] = str(self.bootstrap.get("summary", {}).get("volRegimeTenor") or "1M")
                params["lookbackDays"] = lookback_days or self.lookback_days
            try:
                versions[panel] = payload_revision(self.panel_payload(panel, params))
            except ValueError:
                continue
        return versions

    def state_payload(self) -> dict[str, Any]:
        return {
            "snapshot": copy.deepcopy(self.bootstrap.get("snapshot", {})),
            "snapshotVersion": str(self.snapshot_id),
            "panelVersions": self.panel_versions(),
            "availablePanels": list(VERSIONED_PANELS),
        }


def dashboard_panel_payloads(
    snapshot: RuntimeDashboardSnapshot,
    panels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for panel, params in panels.items():
        try:
            payload[panel] = snapshot.panel_payload(panel, params)
        except ValueError:
            continue
    return payload


def payload_revision(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.blake2s(encoded, digest_size=8).hexdigest()


def vol_regime_from_terms(
    *,
    current_terms: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    tenor: str,
    lookback_days: int,
    latest_ts_ms: int,
) -> dict[str, Any]:
    start_ts_ms = latest_ts_ms - lookback_days * MS_PER_DAY
    values = [
        float(row["atm_iv"])
        for row in history_rows
        if row.get("tenor") == tenor
        and row.get("atm_iv") is not None
        and start_ts_ms <= int(row["ts_ms"]) <= latest_ts_ms
    ]
    current = next(
        (
            float(row["atm_iv"])
            for row in current_terms
            if row.get("tenor") == tenor and row.get("atm_iv") is not None
        ),
        None,
    )
    if current is not None:
        values.append(current)
    if not values:
        return empty_vol_regime(tenor, lookback_days, latest_ts_ms=latest_ts_ms)
    min_iv = min(values)
    max_iv = max(values)
    rank = ((current - min_iv) / (max_iv - min_iv) * 100) if current is not None and max_iv > min_iv else None
    percentile = (
        sum(1 for value in values if current is not None and value <= current) / len(values) * 100
        if current is not None
        else None
    )
    return {
        "tenor": tenor,
        "lookbackDays": lookback_days,
        "latestTsMs": latest_ts_ms,
        "currentAtmIv": current,
        "minAtmIv": min_iv,
        "maxAtmIv": max_iv,
        "ivRank": _round(rank),
        "ivPercentile": _round(percentile),
        "sampleCount": len(values),
    }


def empty_vol_regime(
    tenor: str,
    lookback_days: int,
    *,
    latest_ts_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "tenor": tenor,
        "lookbackDays": lookback_days,
        "latestTsMs": latest_ts_ms,
        "currentAtmIv": None,
        "minAtmIv": None,
        "maxAtmIv": None,
        "ivRank": None,
        "ivPercentile": None,
        "sampleCount": 0,
    }


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)
