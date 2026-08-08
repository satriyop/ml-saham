"""Accum risk gate panel: schema-15 risk.gate_evaluations + forward excess.

Live ai-saham ACCUM captures store the authoritative per-gate audit under
``features_by_window.<window>.risk.gate_evaluations`` (schema 15). Coarse
``trade_setup.blocking_gates`` is presentation/action transport only and must
not be the sole attribution source for current production challenges.

Top-level ``payload["trade_setup"]`` and window ``trade_setup.blocking_gates``
without a risk audit are historical/fixture shapes — they are not production
current-schema evidence.
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

# Outcomes that count as a blocked component (1.0) for the hard-gate panel.
_BLOCKED_OUTCOMES = frozenset({"triggered", "blocked_on_missing"})
# Outcomes that count as not blocked (0.0).
_CLEAR_OUTCOMES = frozenset({"pass", "skipped", "not_evaluated"})


def _alias_to_gate_key(policy: ChallengeExecutionPolicy) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in policy.components:
        m[c.key.lower()] = c.key
        for a in c.aliases:
            m[str(a).lower()] = c.key
    return m


def _gate_key_from_name(name: str, aliases: dict[str, str]) -> str | None:
    key = aliases.get(name.lower()) or aliases.get(name.replace("Gate", "").lower())
    if key is not None:
        return key
    snake = "".join(("_" + ch.lower() if ch.isupper() else ch) for ch in name).lstrip(
        "_"
    )
    return aliases.get(snake.lower())


def _resolve_risk_audit(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the window risk audit dict, or None if absent/unusable."""
    window = _pick_window_blob(payload)
    if not isinstance(window, dict):
        return None
    risk = window.get("risk")
    if not isinstance(risk, dict) or not risk:
        return None
    return risk


def extract_gate_components(
    payload: dict[str, Any],
    policy: ChallengeExecutionPolicy,
) -> dict[str, float] | None:
    """Per-gate fire flags from schema-15 ``risk.gate_evaluations``.

    Mapping (adapter/conformance v2):

    - ``triggered`` / ``blocked_on_missing`` -> ``1.0`` (blocked)
    - ``pass`` / ``skipped`` / ``not_evaluated`` -> ``0.0`` (not blocked)

    Returns ``None`` when the current-schema risk audit is absent or malformed.
    Never invents an all-clear and never assigns a blocked action to an
    arbitrary first-enabled gate.
    """
    aliases = _alias_to_gate_key(policy)
    enabled = {c.key for c in policy.enabled_components()}
    if not enabled:
        return None

    risk = _resolve_risk_audit(payload)
    if risk is None:
        return None

    evaluations = risk.get("gate_evaluations")
    if not isinstance(evaluations, list):
        return None

    found = {k: 0.0 for k in enabled}
    saw_usable_row = False
    for row in evaluations:
        if not isinstance(row, dict):
            return None
        name = str(row.get("gate") or "").strip()
        outcome = str(row.get("outcome") or "").strip()
        if not name or not outcome:
            return None
        if outcome not in _BLOCKED_OUTCOMES and outcome not in _CLEAR_OUTCOMES:
            return None
        key = _gate_key_from_name(name, aliases)
        if key not in enabled:
            # Unknown / disabled gate names are ignored for the panel vector.
            continue
        saw_usable_row = True
        found[key] = 1.0 if outcome in _BLOCKED_OUTCOMES else 0.0

    if not saw_usable_row and evaluations:
        # Evaluations present but none mapped to enabled components — not
        # extractable for this policy vector.
        return None
    if not evaluations:
        # Empty audit list with a risk object means "risk ran, no gates
        # configured/recorded" — treat as all-clear only when risk is present.
        return found
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
        n_unextractable = 0
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
                n_unextractable += 1
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
                n_unextractable += 1
                continue
            if any(v > 0 for v in comps.values()):
                n_blocked += 1
            candidates.append((ticker, date, comps))

        if n_unextractable:
            notes.append(
                f"skipped {n_unextractable} rows missing/malformed "
                "features_by_window.*.risk.gate_evaluations"
            )
        if not candidates:
            return [], notes + [
                "no accum rows with schema-15 risk.gate_evaluations audit"
            ]

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
        notes.append(
            "source=features_by_window.*.risk.gate_evaluations (adapter v2; "
            "no first-enabled-gate fallback)"
        )
        return out, notes
