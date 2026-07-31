"""Accum risk gate panel: trade_setup blocking_gates + forward excess.

Live ai-saham ACCUM captures nest RiskEngine output under
``features_by_window.<window>.trade_setup`` (same ADR-056 window as signal /
sleeves). Top-level ``payload["trade_setup"]`` is fixture/legacy only.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import PanelRow, _pick_window_blob, build_forward_excess
from ml_saham.challenge.types import ChallengeExecutionPolicy
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.observation_cohort import fetch_accum_observation_raw


def _alias_to_gate_key(policy: ChallengeExecutionPolicy) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in policy.components:
        m[c.key.lower()] = c.key
        for a in c.aliases:
            m[str(a).lower()] = c.key
    return m


def _resolve_trade_setup(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer window-nested trade_setup (live ADR-056), else top-level legacy."""
    window = _pick_window_blob(payload)
    if isinstance(window, dict):
        wts = window.get("trade_setup")
        if isinstance(wts, dict) and wts:
            return wts
    top = payload.get("trade_setup")
    if isinstance(top, dict) and top:
        return top
    return None


def _gate_key_from_name(name: str, aliases: dict[str, str]) -> str | None:
    key = aliases.get(name.lower()) or aliases.get(name.replace("Gate", "").lower())
    if key is not None:
        return key
    snake = "".join(("_" + ch.lower() if ch.isupper() else ch) for ch in name).lstrip(
        "_"
    )
    return aliases.get(snake.lower())


def extract_gate_components(
    payload: dict[str, Any],
    policy: ChallengeExecutionPolicy,
) -> dict[str, float] | None:
    """Per-gate fire flags (1.0 fired / 0.0 clear). None if no trade_setup blob."""
    aliases = _alias_to_gate_key(policy)
    enabled = {c.key for c in policy.enabled_components()}
    if not enabled:
        return None

    ts = _resolve_trade_setup(payload)
    if ts is None:
        # Do not invent all-clear — missing setup is not "no gates fired"
        return None

    found = {k: 0.0 for k in enabled}
    gates = ts.get("blocking_gates")
    if isinstance(gates, list):
        for g in gates:
            name = str(g or "").strip()
            if not name:
                continue
            key = _gate_key_from_name(name, aliases)
            if key in enabled:
                found[key] = 1.0
    # honor action BLOCKED* without named gates → first enabled gate
    action = str(ts.get("action") or "").upper()
    if action in ("BLOCKED", "BLOCKED_STRUCTURAL", "BLOCKED_EXECUTION") and not any(
        v > 0 for v in found.values()
    ):
        first = next(iter(enabled))
        found[first] = 1.0
    return found


def build_gate_panel(
    db_path: Path | str,
    policy: ChallengeExecutionPolicy,
    horizons: tuple[int, ...],
    primary_horizon: int,
    *,
    compatibility_id: str | None = None,
) -> tuple[list[PanelRow], list[str]]:
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            return [], ["learning_observations missing"]
        rows_raw, cohort_notes, _ = fetch_accum_observation_raw(
            conn, preferred_compatibility_id=compatibility_id
        )
        notes.extend(cohort_notes)

        candidates: list[tuple[str, str, dict[str, float]]] = []
        n_blocked = 0
        for row in rows_raw:
            if isinstance(row, sqlite3.Row):
                _p, _c, payload_json = (
                    row["purpose"],
                    row["captured_at"],
                    row["decision_payload_json"],
                )
            else:
                _p, _c, payload_json = row[0], row[1], row[2]
            try:
                payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                continue
            ticker = str(payload.get("ticker") or "").upper()
            date = str(
                payload.get("session_date")
                or payload.get("snapshot_date")
                or payload.get("as_of")
                or payload.get("date")
                or ""
            )
            if "T" in date:
                date = date.split("T", 1)[0]
            if not ticker or not date:
                continue
            comps = extract_gate_components(payload, policy)
            if not comps:
                continue
            if any(v > 0 for v in comps.values()):
                n_blocked += 1
            candidates.append((ticker, date, comps))

        if not candidates:
            return [], notes + ["no accum rows with trade_setup gate fields"]

        tickers = sorted({t for t, _, _ in candidates})
        excess_map = build_forward_excess(conn, tickers, horizons)
        if not excess_map:
            return [], notes + ["could not build IHSG-aligned forward excess"]

        out: list[PanelRow] = []
        dropped = 0
        for ticker, date, comps in candidates:
            ex = excess_map.get((ticker, date))
            if not ex or primary_horizon not in ex:
                dropped += 1
                continue
            out.append(PanelRow(ticker=ticker, date=date, components=comps, excess=ex))
        if dropped:
            notes.append(f"dropped {dropped} rows missing primary H={primary_horizon}")
        br = (n_blocked / len(candidates)) if candidates else 0.0
        notes.append(
            f"gate_panel n={len(out)} block_rate_raw={br:.0%} policy={policy.policy_id}"
        )
        notes.append(
            "decision_type=gate · metric=mean_excess_among_allowed (not sleeve rank IC)"
        )
        return out, notes
