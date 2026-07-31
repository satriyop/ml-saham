"""Diagnostic bag panel: observation features + production control score + excess labels.

Live ACCUM captures nest signal / fingerprint / candidate under
``features_by_window.<window>`` (ADR-056). Root-level ``signal`` /
``sub_signal_fingerprint`` are empty on production payloads.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import (
    _pick_window_blob,
    build_forward_excess,
    extract_components,
)
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.scorers import score_production
from ml_saham.challenge.types import DiagnosticSpec, PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.observation_cohort import fetch_accum_observation_raw


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


def _payload_views(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return (signal, fingerprint, candidate, root_or_window) preferring ADR-056 window."""
    window = _pick_window_blob(payload)
    if isinstance(window, dict) and window:
        sig = window.get("signal") if isinstance(window.get("signal"), dict) else {}
        fp = (
            window.get("sub_signal_fingerprint")
            if isinstance(window.get("sub_signal_fingerprint"), dict)
            else {}
        )
        cand = window.get("candidate") if isinstance(window.get("candidate"), dict) else {}
        # Prefer window signal/fp; fall back to root for hybrid fixtures
        if not sig:
            top = payload.get("signal")
            sig = top if isinstance(top, dict) else {}
        if not fp:
            top_fp = payload.get("sub_signal_fingerprint")
            fp = top_fp if isinstance(top_fp, dict) else {}
        if not cand:
            top_c = payload.get("candidate")
            cand = top_c if isinstance(top_c, dict) else {}
        return sig, fp, cand, window

    sig = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    fp = (
        payload.get("sub_signal_fingerprint")
        if isinstance(payload.get("sub_signal_fingerprint"), dict)
        else {}
    )
    cand = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    return sig, fp, cand, payload


def _group_score_from_signal(signal: dict[str, Any], group_name: str) -> float | None:
    at = signal.get("alpha_trigger_score") if isinstance(signal, dict) else None
    # assessment may mirror alpha_trigger
    if not isinstance(at, dict):
        ass = signal.get("assessment") if isinstance(signal.get("assessment"), dict) else {}
        at = ass.get("alpha_trigger_score") if isinstance(ass, dict) else None
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
    for key in ("evidence_groups", "group_contributions", "groups"):
        blob = signal.get(key) if isinstance(signal, dict) else None
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


def _group_score(payload: dict[str, Any], group_name: str) -> float | None:
    signal, _fp, _cand, root = _payload_views(payload)
    sc = _group_score_from_signal(signal, group_name)
    if sc is not None:
        return sc
    # root-level group maps (rare / fixture)
    for key in ("evidence_groups", "group_contributions", "groups"):
        blob = payload.get(key) if isinstance(payload, dict) else None
        if blob is None and isinstance(root, dict):
            blob = root.get(key)
        if isinstance(blob, list):
            for g in blob:
                if not isinstance(g, dict):
                    continue
                if str(g.get("group") or g.get("name") or "").lower() == group_name.lower():
                    raw = g.get("score")
                    if isinstance(raw, (int, float)):
                        return float(raw)
    return None


def _fingerprint_get(
    fp: dict[str, Any],
    key: str,
    *,
    aliases: tuple[str, ...] = (),
) -> float | None:
    for k in (key, *aliases):
        if isinstance(fp.get(k), (int, float)):
            return float(fp[k])
    return None


def _peer_breadth(
    payload: dict[str, Any],
    *,
    fingerprint: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> float | None:
    signal, fp0, cand0, root = _payload_views(payload)
    del signal
    fp = fingerprint if fingerprint is not None else fp0
    cand = candidate if candidate is not None else cand0
    for src in (cand, root, payload):
        if not isinstance(src, dict):
            continue
        for path in (
            ("sector_context", "peer_breadth"),
            ("sector_context", "breadth"),
            ("diagnostics", "peer_breadth"),
            ("sector_breadth",),
            ("peer_breadth",),
        ):
            cur: Any = src
            ok = True
            for p in path:
                if not isinstance(cur, dict) or p not in cur:
                    ok = False
                    break
                cur = cur[p]
            if ok and isinstance(cur, (int, float)):
                return float(cur)
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
    signal, fp, cand, root = _payload_views(payload)

    def fp_val(key: str) -> float | None:
        aliases: tuple[str, ...] = ()
        for f in spec.enabled_features():
            if f.key == key:
                aliases = tuple(f.aliases)
                break
        return _fingerprint_get(fp, key, aliases=aliases)

    if spec.diagnostic_id == "mce.screen_display":
        for k in enabled:
            if k in mctx and isinstance(mctx[k], (int, float)):
                found[k] = float(mctx[k])
        # payload-embedded market context (root or window)
        for nest_src in (payload, root):
            if not isinstance(nest_src, dict):
                continue
            for nest in ("market_context", "mce", "diagnostics"):
                blob = nest_src.get(nest)
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
        sc = _group_score_from_signal(signal, "sector_context")
        if sc is None:
            sc = _group_score(payload, "sector_context")
        if sc is not None and "sector_context_score" in enabled:
            found["sector_context_score"] = sc
        pb = _peer_breadth(payload, fingerprint=fp, candidate=cand)
        if pb is not None and "peer_breadth" in enabled:
            found["peer_breadth"] = pb

    elif spec.diagnostic_id == "institutional.accumulation_bag":
        ig = _group_score_from_signal(signal, "institutional_flow")
        if ig is None:
            ig = _group_score(payload, "institutional_flow")
        if ig is not None and "institutional_flow_score" in enabled:
            found["institutional_flow_score"] = ig
        for k in (
            "ia_foreign_participation",
            "ia_domestic_buy_vwap_distance",
        ):
            if k not in enabled:
                continue
            v = fp_val(k)
            if v is not None:
                found[k] = v

    elif spec.diagnostic_id == "company_quality.bag":
        cq = _group_score_from_signal(signal, "company_quality_context")
        if cq is None:
            cq = _group_score(payload, "company_quality_context")
        if cq is not None and "company_quality_score" in enabled:
            found["company_quality_score"] = cq
        for k in ("cq_valuation_score", "tp_liquidity_score", "tp_volatility_score"):
            if k not in enabled:
                continue
            v = fp_val(k)
            if v is not None:
                found[k] = v
        # common live aggregate when axis valuation missing
        if "company_quality_score" in enabled and "company_quality_score" not in found:
            agg = _fingerprint_get(fp, "cq_aggregate_score", aliases=("cq_aggregate",))
            if agg is not None:
                found["company_quality_score"] = agg

    else:
        for k in enabled:
            v = fp_val(k)
            if v is not None:
                found[k] = v
        for k in enabled:
            if k in found:
                continue
            gs = _group_score_from_signal(signal, k)
            if gs is None:
                gs = _group_score(payload, k)
            if gs is not None:
                found[k] = gs

    if not found:
        return None
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
    *,
    compatibility_id: str | None = None,
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

        rows_raw, cohort_notes, _ = fetch_accum_observation_raw(
            conn, preferred_compatibility_id=compatibility_id
        )
        notes.extend(cohort_notes)
        if any("decision_payload_json missing" in n for n in cohort_notes):
            return [], notes

        candidates: list[tuple[str, str, dict[str, float], float]] = []
        for row in rows_raw:
            if isinstance(row, sqlite3.Row):
                payload_json = row["decision_payload_json"]
            else:
                payload_json = row[2]
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
