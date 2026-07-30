"""Accum signal panel: signal.raw_score + group features + forward excess."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import ACCUM_PURPOSES, PanelRow, build_forward_excess
from ml_saham.challenge.types import PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _group_scores(payload: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    at = signal.get("alpha_trigger_score") if isinstance(signal, dict) else None
    gcs = None
    if isinstance(at, dict):
        gcs = at.get("group_contributions")
    if not isinstance(gcs, list):
        gcs = payload.get("group_contributions")
    if isinstance(gcs, list):
        for g in gcs:
            if not isinstance(g, dict):
                continue
            name = str(g.get("group") or g.get("name") or "").lower()
            sc = _f(g.get("score"))
            if name and sc is not None:
                out[name] = sc
    return out


def extract_signal_components(
    payload: dict[str, Any],
    policy: PolicySnapshot,
) -> dict[str, float] | None:
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    raw = _f(signal.get("raw_score"))
    if raw is None:
        raw = _f(signal.get("raw_exact_score"))
    if raw is None:
        raw = _f(signal.get("score"))
    if raw is None:
        fp = payload.get("sub_signal_fingerprint")
        if isinstance(fp, dict):
            raw = _f(fp.get("raw_signal_score"))
    if raw is None:
        return None

    found: dict[str, float] = {"production_raw_score": raw}
    groups = _group_scores(payload)
    for c in policy.components:
        if c.key == "production_raw_score":
            continue
        if c.key in groups:
            found[c.key] = groups[c.key]
            continue
        for a in c.aliases:
            if a.lower() in groups:
                found[c.key] = groups[a.lower()]
                break

    # need raw + at least one group feature when features exist
    feat_keys = [k for k in policy.feature_keys()]
    if feat_keys:
        present = sum(1 for k in feat_keys if k in found)
        if present < 1:
            # still allow raw-only rows (fill zeros) for dense raw_score series
            pass
    for k in feat_keys:
        found.setdefault(k, 0.0)
    return found


def build_signal_panel(
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
            comps = extract_signal_components(payload, policy)
            if not comps:
                continue
            candidates.append((ticker, date, comps))

        if not candidates:
            return [], notes + ["no accum signal rows with raw_score"]

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
        notes.append(f"signal_panel n={len(out)} policy={policy.policy_id}")
        return out, notes
