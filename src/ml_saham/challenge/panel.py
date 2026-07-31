"""Build challenge panel: observation components + candle forward labels."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml_saham.challenge.types import PolicySnapshot
from ml_saham.data.aisaham_read import connect, load_candles, table_exists
from ml_saham.data.observation_cohort import (
    ACCUM_PURPOSE_LIKE,
    ACCUM_PURPOSES,
    fetch_accum_observation_raw,
    list_compatibility_cohorts,
    resolve_compatibility_id,
)

# Re-export for callers / tests that import from challenge.panel
__all__ = [
    "ACCUM_PURPOSES",
    "PanelRow",
    "build_forward_excess",
    "build_panel",
    "extract_components",
    "fetch_accum_observation_raw",
    "list_accum_compatibility_cohorts",
    "load_observation_rows",
    "resolve_accum_compatibility_id",
]


@dataclass
class PanelRow:
    ticker: str
    date: str
    components: dict[str, float]  # key -> points in [0, weight] space or raw scores
    excess: dict[int, float]  # horizon -> excess return vs IHSG


def _session_forward_map(
    closes_by_date: dict[str, float],
    dates_sorted: list[str],
    horizon: int,
) -> dict[str, float]:
    """Map date -> close[t+H]/close[t]-1 using session index."""
    out: dict[str, float] = {}
    idx = {d: i for i, d in enumerate(dates_sorted)}
    for d, i in idx.items():
        j = i + horizon
        if j >= len(dates_sorted):
            continue
        c0 = closes_by_date.get(d)
        c1 = closes_by_date.get(dates_sorted[j])
        if c0 is None or c1 is None or c0 <= 0:
            continue
        out[d] = c1 / c0 - 1.0
    return out


def build_forward_excess(
    conn: sqlite3.Connection,
    tickers: list[str],
    horizons: tuple[int, ...],
) -> dict[tuple[str, str], dict[int, float]]:
    """(ticker, date) -> {H: excess vs IHSG}."""
    need = list(set(tickers) | {"IHSG"})
    candles = load_candles(conn, need)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))

    ihsg_rows = sorted(by_t.get("IHSG") or [], key=lambda x: x[0])
    if len(ihsg_rows) < max(horizons) + 2:
        return {}
    ihsg_dates = [d for d, _ in ihsg_rows]
    ihsg_close = {d: c for d, c in ihsg_rows}
    ihsg_fwd = {
        h: _session_forward_map(ihsg_close, ihsg_dates, h) for h in horizons
    }

    result: dict[tuple[str, str], dict[int, float]] = {}
    for t in tickers:
        rows = sorted(by_t.get(t) or [], key=lambda x: x[0])
        if len(rows) < max(horizons) + 2:
            continue
        dates = [d for d, _ in rows]
        closes = {d: c for d, c in rows}
        t_fwd = {h: _session_forward_map(closes, dates, h) for h in horizons}
        for d in dates:
            ex: dict[int, float] = {}
            for h in horizons:
                if d not in t_fwd[h] or d not in ihsg_fwd[h]:
                    continue
                ex[h] = t_fwd[h][d] - ihsg_fwd[h][d]
            if ex:
                result[(t, d)] = ex
    return result


def _alias_lookup(policy: PolicySnapshot) -> dict[str, str]:
    """Map any alias or key -> canonical component key."""
    m: dict[str, str] = {}
    for c in policy.components:
        m[c.key.lower()] = c.key
        for a in c.aliases:
            m[a.lower()] = c.key
    return m


def _ingest_component_list(
    items: list[Any],
    aliases: dict[str, str],
    found: dict[str, float],
) -> None:
    """Ingest [{key, score_points|score}, ...] into found map."""
    for item in items:
        if not isinstance(item, dict):
            continue
        k = str(item.get("key") or "").lower()
        if k not in aliases:
            continue
        # Prefer production score_points; fall back to score
        raw = item.get("score_points")
        if raw is None:
            raw = item.get("score")
        if raw is None:
            continue
        try:
            found[aliases[k]] = float(raw)
        except (TypeError, ValueError):
            continue


def _pick_window_blob(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer features_by_window[canonical_window], else 7, else first dict."""
    fbw = payload.get("features_by_window")
    if not isinstance(fbw, dict) or not fbw:
        return None
    preferred = []
    cw = payload.get("canonical_window")
    if cw is not None:
        preferred.append(str(cw))
    preferred.extend(["7", "30", "90"])
    for key in preferred:
        blob = fbw.get(key)
        if isinstance(blob, dict):
            return blob
    for blob in fbw.values():
        if isinstance(blob, dict):
            return blob
    return None


def extract_components(payload: dict[str, Any], policy: PolicySnapshot) -> dict[str, float] | None:
    """Adaptive extract of component points from observation payload.

    Supports:
    - ai-saham ADR-056 style: features_by_window.*.candidate.accum_score_breakdown
    - fixture / legacy: top-level signal.flow_evidence.flow_signals
    """
    aliases = _alias_lookup(policy)
    found: dict[str, float] = {}

    # --- A) Real ai-saham accum observation (preferred) ---
    window = _pick_window_blob(payload)
    if window is not None:
        cand = window.get("candidate") if isinstance(window.get("candidate"), dict) else {}
        breakdown = cand.get("accum_score_breakdown") if isinstance(cand, dict) else None
        if isinstance(breakdown, dict):
            comps = breakdown.get("components")
            if isinstance(comps, list):
                _ingest_component_list(comps, aliases, found)
            # also breakdown map: {cons: 9.5, streak: 3.3, ...}
            br = breakdown.get("breakdown")
            if isinstance(br, dict):
                for k, v in br.items():
                    kl = str(k).lower()
                    if kl in aliases and aliases[kl] not in found and isinstance(v, (int, float)):
                        found[aliases[kl]] = float(v)
        # nested signal.flow_evidence under window
        wsig = window.get("signal") if isinstance(window.get("signal"), dict) else {}
        fe = wsig.get("flow_evidence") if isinstance(wsig, dict) else {}
        if isinstance(fe, dict) and isinstance(fe.get("flow_signals"), list):
            _ingest_component_list(fe["flow_signals"], aliases, found)

    # --- B) Top-level legacy / fixture shape ---
    signal = payload.get("signal") or {}
    if isinstance(signal, dict):
        flow_ev = signal.get("flow_evidence") or {}
        if isinstance(flow_ev, dict) and isinstance(flow_ev.get("flow_signals"), list):
            _ingest_component_list(flow_ev["flow_signals"], aliases, found)

    # --- C) Fingerprint fallbacks (scaled) ---
    fp = payload.get("sub_signal_fingerprint") or {}
    if not fp and window is not None:
        fp = window.get("sub_signal_fingerprint") or {}
    if isinstance(fp, dict):
        fp_map = {
            "rsi_at_signal": "rsi_headroom",
            "vwap_position_at_signal": "vwap_discount",
            "bb_width_pctile_at_signal": "bb_squeeze",
            "ia_foreign_participation": "foreign_flow_ratio",
            "foreign_concentration_at_signal": "consistency",
            # P0 BCI / sector breadth when not in flow_signals breakdown
            "bci_score": "bci",
            "bci_points": "bci",
            "inst_score": "bci",
            "tier1_concentration": "bci",
            "sector_breadth": "sector_breadth",
            "peer_breadth": "sector_breadth",
            "sector_breadth_bonus": "sector_breadth",
            "breadth_at_signal": "sector_breadth",
        }
        for src, dest in fp_map.items():
            if dest in found:
                continue
            if src in fp and isinstance(fp[src], (int, float)):
                w = next((c.weight for c in policy.components if c.key == dest), 10.0)
                val = float(fp[src])
                if dest == "rsi_headroom":
                    score = max(0.0, min(1.0, (val - 25.0) / 50.0)) * w
                elif dest == "vwap_discount":
                    score = max(0.0, min(1.0, abs(val) * 10)) * w
                elif dest == "bb_squeeze":
                    score = max(0.0, min(1.0, 1.0 - val)) * w
                elif dest == "sector_breadth":
                    # production: often fraction 0–1 or already points 0–10
                    score = val * w if val <= 1.0 else min(w, val)
                elif dest == "bci":
                    score = val * w if val <= 1.0 else min(w, max(0.0, val))
                else:
                    score = max(0.0, min(1.0, abs(val))) * w
                found[dest] = score

    # --- D) Candidate / top-level extras for P0 sleeves ---
    cand = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    if window is not None and isinstance(window.get("candidate"), dict):
        cand = {**cand, **window["candidate"]}
    for src, dest in (
        ("sector_breadth", "sector_breadth"),
        ("peer_breadth", "sector_breadth"),
        ("sector_breadth_bonus", "sector_breadth"),
        ("bci", "bci"),
        ("bci_points", "bci"),
    ):
        if dest in found:
            continue
        raw = cand.get(src) if isinstance(cand, dict) else None
        if isinstance(raw, (int, float)):
            w = next((c.weight for c in policy.components if c.key == dest), 10.0)
            val = float(raw)
            found[dest] = val * w if val <= 1.0 else min(w, max(0.0, val))

    enabled_keys = {c.key for c in policy.enabled_components()}
    present = enabled_keys & set(found)
    if len(present) < 3:
        return None
    for k in enabled_keys:
        found.setdefault(k, 0.0)
    return {k: found[k] for k in enabled_keys}


def list_accum_compatibility_cohorts(
    conn: sqlite3.Connection,
    *,
    purposes: tuple[str, ...] = ACCUM_PURPOSES,
) -> list[tuple[str, int, str | None]]:
    """ACCUM cohorts — see ``ml_saham.data.observation_cohort``."""
    return list_compatibility_cohorts(
        conn, purposes=purposes, purpose_like=ACCUM_PURPOSE_LIKE
    )


def resolve_accum_compatibility_id(
    conn: sqlite3.Connection,
    *,
    preferred: str | None = None,
    purposes: tuple[str, ...] = ACCUM_PURPOSES,
) -> tuple[str | None, list[str]]:
    """Pick exactly one ACCUM compatibility cohort (never mix rulebooks)."""
    return resolve_compatibility_id(
        conn,
        purposes=purposes,
        purpose_like=ACCUM_PURPOSE_LIKE,
        preferred=preferred,
        family="ACCUM",
    )


def load_observation_rows(
    conn: sqlite3.Connection,
    policy: PolicySnapshot,
    *,
    compatibility_id: str | None = None,
    preferred_compatibility_id: str | None = None,
) -> tuple[list[tuple[str, str, dict[str, float], str]], list[str]]:
    """Return ``((ticker, date, components, captured_at), …), notes``.

    Applies single-cohort ``compatibility_id`` discipline when the column exists.
    """
    if not table_exists(conn, "learning_observations"):
        return [], ["learning_observations missing"]

    rows, notes, _resolved = fetch_accum_observation_raw(
        conn,
        compatibility_id=compatibility_id,
        preferred_compatibility_id=preferred_compatibility_id,
    )

    out: list[tuple[str, str, dict[str, float], str]] = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            purpose, captured_at, payload_json = (
                row["purpose"],
                row["captured_at"],
                row["decision_payload_json"],
            )
        else:
            purpose, captured_at, payload_json = row[0], row[1], row[2]
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
        # session_date may be date-only or ISO datetime
        if "T" in date:
            date = date.split("T", 1)[0]
        if not ticker or not date:
            continue
        comps = extract_components(payload, policy)
        if not comps:
            continue
        out.append((ticker, date, comps, str(captured_at or "")))
    return out, notes


def build_panel(
    db_path: Path | str,
    policy: PolicySnapshot,
    horizons: tuple[int, ...],
    primary_horizon: int,
    *,
    compatibility_id: str | None = None,
) -> tuple[list[PanelRow], list[str]]:
    """Build labeled panel; notes collect non-fatal warnings.

    When ``learning_observations.compatibility_id`` exists, loads **one** cohort
    only (explicit ``compatibility_id`` or auto largest). Never mixes rulebooks.
    """
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        raw, cohort_notes = load_observation_rows(
            conn,
            policy,
            preferred_compatibility_id=compatibility_id,
        )
        notes.extend(cohort_notes)
        if not raw:
            return [], notes + ["no extractable accum observations with components"]

        # dedupe (ticker, date) keep last by captured_at order
        by_key: dict[tuple[str, str], tuple[dict[str, float], str]] = {}
        for ticker, date, comps, cap in raw:
            by_key[(ticker, date)] = (comps, cap)
        tickers = sorted({t for t, _ in by_key})
        excess_map = build_forward_excess(conn, tickers, horizons)
        if not excess_map:
            return [], notes + [
                "could not build IHSG-aligned forward excess (check IHSG candles)"
            ]

        rows: list[PanelRow] = []
        dropped_primary = 0
        for (ticker, date), (comps, _) in sorted(by_key.items()):
            ex = excess_map.get((ticker, date))
            if not ex or primary_horizon not in ex:
                dropped_primary += 1
                continue
            rows.append(PanelRow(ticker=ticker, date=date, components=comps, excess=ex))

        if dropped_primary:
            notes.append(f"dropped {dropped_primary} rows missing primary H={primary_horizon}")
        notes.append(f"panel_rows={len(rows)} unique_tickers={len({r.ticker for r in rows})}")
        return rows, notes
