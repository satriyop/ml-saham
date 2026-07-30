"""Accum risk gate panel: trade_setup blocking_gates + forward excess."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import ACCUM_PURPOSES, PanelRow, build_forward_excess
from ml_saham.challenge.types import PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists


def _alias_to_gate_key(policy: PolicySnapshot) -> dict[str, str]:
    m: dict[str, str] = {}
    for c in policy.components:
        m[c.key.lower()] = c.key
        for a in c.aliases:
            m[str(a).lower()] = c.key
    return m


def extract_gate_components(
    payload: dict[str, Any],
    policy: PolicySnapshot,
) -> dict[str, float] | None:
    """Per-gate fire flags (1.0 fired / 0.0 clear). Always returns enabled keys."""
    aliases = _alias_to_gate_key(policy)
    enabled = {c.key for c in policy.enabled_components()}
    if not enabled:
        return None

    found = {k: 0.0 for k in enabled}
    ts = payload.get("trade_setup") if isinstance(payload.get("trade_setup"), dict) else {}
    gates = ts.get("blocking_gates") if isinstance(ts, dict) else None
    if isinstance(gates, list):
        for g in gates:
            name = str(g or "").strip()
            if not name:
                continue
            key = aliases.get(name.lower()) or aliases.get(name.replace("Gate", "").lower())
            # BandarGate → bandar_gate via aliases
            if key is None:
                # try snake of CamelGate
                snake = "".join(
                    ("_" + ch.lower() if ch.isupper() else ch) for ch in name
                ).lstrip("_")
                key = aliases.get(snake.lower())
            if key in enabled:
                found[key] = 1.0
    # also honor action BLOCKED without named gates → mark all enabled as fired
    action = str(ts.get("action") or "").upper() if isinstance(ts, dict) else ""
    if action in ("BLOCKED", "BLOCKED_STRUCTURAL", "BLOCKED_EXECUTION") and not any(
        v > 0 for v in found.values()
    ):
        # unknown gate name — treat as structural block on first enabled gate
        first = next(iter(enabled))
        found[first] = 1.0
    return found


def build_gate_panel(
    db_path: Path | str,
    policy: PolicySnapshot,
    horizons: tuple[int, ...],
    primary_horizon: int,
) -> tuple[list[PanelRow], list[str]]:
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            return [], ["learning_observations missing"]
        purpose_filter = ",".join("?" * len(ACCUM_PURPOSES))
        rows_raw = conn.execute(
            f"SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
            f"WHERE purpose IN ({purpose_filter}) ORDER BY captured_at ASC",
            ACCUM_PURPOSES,
        ).fetchall()
        if not rows_raw:
            rows_raw = conn.execute(
                "SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
                "WHERE purpose LIKE '%ACCUM%' OR purpose LIKE '%accum%' "
                "ORDER BY captured_at ASC"
            ).fetchall()

        candidates: list[tuple[str, str, dict[str, float]]] = []
        n_blocked = 0
        for _p, _c, payload_json in rows_raw:
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
            out.append(
                PanelRow(ticker=ticker, date=date, components=comps, excess=ex)
            )
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
