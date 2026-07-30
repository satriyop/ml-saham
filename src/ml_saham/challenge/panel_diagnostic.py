"""Diagnostic bag panel: observation features + production control score + excess labels."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import (
    ACCUM_PURPOSES,
    build_forward_excess,
    extract_components,
)
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.scorers import score_production
from ml_saham.challenge.types import DiagnosticSpec, PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists


@dataclass
class DiagnosticPanelRow:
    ticker: str
    date: str
    features: dict[str, float]
    production_score: float
    excess: dict[int, float]


_REGIME_MAP = {
    "BULL": 1.0,
    "RISK_ON": 1.0,
    "NEUTRAL": 0.0,
    "RISK_OFF": -0.5,
    "STRESSED": -1.0,
    "BEAR": -1.0,
}


def _load_mctx_by_date(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    """date → feature map from market_context_snapshots."""
    if not table_exists(conn, "market_context_snapshots"):
        return {}
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(market_context_snapshots)").fetchall()
    }
    if "as_of_date" not in cols or "factors_json" not in cols:
        return {}
    has_regime = "regime" in cols
    sql = (
        "SELECT as_of_date, regime, factors_json FROM market_context_snapshots"
        if has_regime
        else "SELECT as_of_date, NULL, factors_json FROM market_context_snapshots"
    )
    out: dict[str, dict[str, float]] = {}
    for as_of, regime, fj in conn.execute(sql).fetchall():
        date = str(as_of or "")
        if "T" in date:
            date = date.split("T", 1)[0]
        if not date:
            continue
        feats: dict[str, float] = {}
        if regime is not None:
            rkey = str(regime).strip().upper()
            feats["regime_score"] = _REGIME_MAP.get(rkey, 0.0)
        try:
            factors = json.loads(fj) if fj else []
        except (TypeError, json.JSONDecodeError):
            factors = []
        if isinstance(factors, list):
            for item in factors:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("key") or "").lower()
                if not name:
                    continue
                raw = item.get("value")
                if raw is None:
                    raw = item.get("score")
                if isinstance(raw, (int, float)):
                    feats[name] = float(raw)
        elif isinstance(factors, dict):
            for k, v in factors.items():
                if isinstance(v, (int, float)):
                    feats[str(k).lower()] = float(v)
        out[date] = feats
    return out


def _group_score(payload: dict[str, Any], group_name: str) -> float | None:
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    # alpha_trigger_score.group_contributions
    at = signal.get("alpha_trigger_score") if isinstance(signal, dict) else None
    if isinstance(at, dict):
        gcs = at.get("group_contributions")
        if isinstance(gcs, list):
            for g in gcs:
                if not isinstance(g, dict):
                    continue
                if str(g.get("group") or "").lower() == group_name.lower():
                    raw = g.get("score")
                    if isinstance(raw, (int, float)):
                        return float(raw)
    # top-level evidence groups
    for key in ("evidence_groups", "group_contributions", "groups"):
        blob = payload.get(key) or (signal.get(key) if isinstance(signal, dict) else None)
        if isinstance(blob, list):
            for g in blob:
                if not isinstance(g, dict):
                    continue
                if str(g.get("group") or g.get("name") or "").lower() == group_name.lower():
                    raw = g.get("score")
                    if isinstance(raw, (int, float)):
                        return float(raw)
        if isinstance(blob, dict) and group_name in blob:
            v = blob[group_name]
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                return float(v["score"])
    return None


def _peer_breadth(payload: dict[str, Any]) -> float | None:
    for path in (
        ("sector_context", "peer_breadth"),
        ("sector_context", "breadth"),
        ("diagnostics", "peer_breadth"),
        ("candidate", "sector_breadth"),
    ):
        cur: Any = payload
        ok = True
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                ok = False
                break
            cur = cur[p]
        if ok and isinstance(cur, (int, float)):
            return float(cur)
    fp = payload.get("sub_signal_fingerprint")
    if isinstance(fp, dict):
        for k in ("peer_breadth", "sector_breadth", "breadth_at_signal"):
            if isinstance(fp.get(k), (int, float)):
                return float(fp[k])
    return None


def extract_diagnostic_features(
    payload: dict[str, Any],
    spec: DiagnosticSpec,
    *,
    mctx: dict[str, float] | None = None,
) -> dict[str, float] | None:
    """Extract enabled diagnostic features; None if too sparse."""
    mctx = mctx or {}
    found: dict[str, float] = {}
    enabled = [f.key for f in spec.enabled_features()]

    if spec.diagnostic_id == "mce.screen_display":
        for k in enabled:
            if k in mctx and isinstance(mctx[k], (int, float)):
                found[k] = float(mctx[k])
        # payload-embedded market context fallback
        for nest in ("market_context", "mce", "diagnostics"):
            blob = payload.get(nest)
            if not isinstance(blob, dict):
                continue
            if "regime" in blob and "regime_score" in enabled and "regime_score" not in found:
                rkey = str(blob.get("regime") or "").strip().upper()
                found["regime_score"] = _REGIME_MAP.get(rkey, 0.0)
            for k in enabled:
                if k in found:
                    continue
                if isinstance(blob.get(k), (int, float)):
                    found[k] = float(blob[k])

    elif spec.diagnostic_id == "sector.peer_context":
        sc = _group_score(payload, "sector_context")
        if sc is not None and "sector_context_score" in enabled:
            found["sector_context_score"] = sc
        pb = _peer_breadth(payload)
        if pb is not None and "peer_breadth" in enabled:
            found["peer_breadth"] = pb

    else:
        # generic: fingerprint + group names matching feature keys
        fp = payload.get("sub_signal_fingerprint")
        if isinstance(fp, dict):
            for k in enabled:
                if isinstance(fp.get(k), (int, float)):
                    found[k] = float(fp[k])
        for k in enabled:
            if k in found:
                continue
            gs = _group_score(payload, k)
            if gs is not None:
                found[k] = gs

    if not found:
        return None
    # require at least one enabled feature present
    present = set(found) & set(enabled)
    if not present:
        return None
    for k in enabled:
        found.setdefault(k, float("nan"))
    return {k: found[k] for k in enabled}


def _production_score_from_comps(
    comps: dict[str, float],
    policy: PolicySnapshot,
) -> float:
    from ml_saham.challenge.panel import PanelRow

    row = PanelRow(ticker="X", date="1970-01-01", components=comps, excess={})
    return float(score_production([row], policy)[0])


def build_diagnostic_panel(
    db_path: Path | str,
    spec: DiagnosticSpec,
    horizons: tuple[int, ...],
    primary_horizon: int,
) -> tuple[list[DiagnosticPanelRow], list[str]]:
    """Build labeled diagnostic panel aligned with accum observations + excess."""
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            return [], ["learning_observations missing"]

        try:
            accum_policy = load_policy("screener.accum.score_weights")
        except KeyError:
            accum_policy = None
            notes.append("accum production policy missing; control_score=0")

        mctx_all = (
            _load_mctx_by_date(conn)
            if spec.diagnostic_id == "mce.screen_display"
            else {}
        )
        if spec.diagnostic_id == "mce.screen_display" and not mctx_all:
            notes.append("market_context_snapshots empty or missing")

        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(learning_observations)").fetchall()
        }
        if "decision_payload_json" not in cols:
            return [], ["learning_observations.decision_payload_json missing"]

        purpose_filter = ",".join("?" * len(ACCUM_PURPOSES))
        sql = (
            f"SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
            f"WHERE purpose IN ({purpose_filter}) ORDER BY captured_at ASC"
        )
        rows_raw = conn.execute(sql, ACCUM_PURPOSES).fetchall()
        if not rows_raw:
            rows_raw = conn.execute(
                "SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
                "WHERE purpose LIKE '%ACCUM%' OR purpose LIKE '%accum%' "
                "ORDER BY captured_at ASC"
            ).fetchall()

        candidates: list[tuple[str, str, dict[str, float], float]] = []
        for _purpose, _cap, payload_json in rows_raw:
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

            mctx = mctx_all.get(date)
            feats = extract_diagnostic_features(payload, spec, mctx=mctx)
            if not feats:
                continue

            prod = 0.0
            if accum_policy is not None:
                comps = extract_components(payload, accum_policy)
                if comps:
                    prod = _production_score_from_comps(comps, accum_policy)
            candidates.append((ticker, date, feats, prod))

        if not candidates:
            return [], notes + ["no diagnostic-extractable observation rows"]

        tickers = sorted({t for t, _, _, _ in candidates})
        excess_map = build_forward_excess(conn, tickers, horizons)
        if not excess_map:
            return [], notes + [
                "could not build IHSG-aligned forward excess (check IHSG candles)"
            ]

        out: list[DiagnosticPanelRow] = []
        dropped = 0
        for ticker, date, feats, prod in candidates:
            ex = excess_map.get((ticker, date))
            if not ex or primary_horizon not in ex:
                dropped += 1
                continue
            finite = [v for v in feats.values() if v == v]  # not NaN
            if not finite:
                dropped += 1
                continue
            out.append(
                DiagnosticPanelRow(
                    ticker=ticker,
                    date=date,
                    features=feats,
                    production_score=prod,
                    excess=ex,
                )
            )
        if dropped:
            notes.append(
                f"dropped {dropped} rows missing primary H={primary_horizon} or empty features"
            )
        notes.append(
            f"diagnostic_panel n={len(out)} diagnostic_id={spec.diagnostic_id}"
        )
        return out, notes
