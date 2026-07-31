"""Accum signal panel: production signal score + group features + forward excess.

Live ai-saham ACCUM captures (ADR-056) nest SignalEngine under
``features_by_window.<window>.signal`` (``assessment.score`` /
``raw_exact_score``), not top-level ``signal.raw_score``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import (
    ACCUM_PURPOSES,
    PanelRow,
    _pick_window_blob,
    build_forward_excess,
)
from ml_saham.challenge.types import PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _resolve_signal_blob(payload: dict[str, Any]) -> dict[str, Any]:
    """Prefer window-nested signal (live ADR-056), else top-level fixture/legacy."""
    window = _pick_window_blob(payload)
    if isinstance(window, dict):
        wsig = window.get("signal")
        if isinstance(wsig, dict) and wsig:
            return wsig
    top = payload.get("signal")
    if isinstance(top, dict):
        return top
    return {}


def _fingerprint_blob(payload: dict[str, Any]) -> dict[str, Any]:
    fp = payload.get("sub_signal_fingerprint")
    if isinstance(fp, dict) and fp:
        return fp
    window = _pick_window_blob(payload)
    if isinstance(window, dict):
        wfp = window.get("sub_signal_fingerprint")
        if isinstance(wfp, dict):
            return wfp
    return {}


def _group_scores(payload: dict[str, Any], signal: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    at = signal.get("alpha_trigger_score") if isinstance(signal, dict) else None
    # assessment may mirror alpha_trigger_score
    if not isinstance(at, dict):
        ass = signal.get("assessment") if isinstance(signal.get("assessment"), dict) else {}
        at = ass.get("alpha_trigger_score") if isinstance(ass, dict) else None
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


def _extract_raw(payload: dict[str, Any], signal: dict[str, Any]) -> float | None:
    """Production score for ranking / baseline.

    Order matches live ai-saham then fixture shapes:
    signal.raw_score → raw_exact_score → score → assessment.score /
    assessment.raw_exact_score → fingerprint.
    """
    ass = signal.get("assessment") if isinstance(signal.get("assessment"), dict) else {}
    for v in (
        signal.get("raw_score"),
        signal.get("raw_exact_score"),
        signal.get("score"),
        signal.get("raw_group_score"),
        ass.get("score") if isinstance(ass, dict) else None,
        ass.get("raw_exact_score") if isinstance(ass, dict) else None,
        ass.get("legacy_conditioned_score") if isinstance(ass, dict) else None,
    ):
        raw = _f(v)
        if raw is not None:
            return raw
    fp = _fingerprint_blob(payload)
    if fp:
        for k in ("raw_signal_score", "raw_score", "score"):
            raw = _f(fp.get(k))
            if raw is not None:
                return raw
    return None


def _flag_fires(payload: dict[str, Any], signal: dict[str, Any], key: str, aliases: tuple[str, ...]) -> float:
    """Return 1.0 if flag fired, else 0.0."""
    names = {key.lower(), *(a.lower() for a in aliases)}
    # list of flag codes
    for src in (
        signal.get("flags"),
        signal.get("active_flags"),
        signal.get("do_no_harm_flags"),
        payload.get("flags"),
    ):
        if isinstance(src, list):
            for item in src:
                if str(item or "").lower().replace("-", "_") in names:
                    return 1.0
        if isinstance(src, dict):
            for k, v in src.items():
                kl = str(k).lower().replace("-", "_")
                if kl in names and v not in (None, False, 0, "0", ""):
                    return 1.0
    # assessment rationale / flags when present
    ass = signal.get("assessment") if isinstance(signal.get("assessment"), dict) else {}
    if isinstance(ass, dict):
        for src in (ass.get("flags"), ass.get("active_flags")):
            if isinstance(src, list):
                for item in src:
                    if str(item or "").lower().replace("-", "_") in names:
                        return 1.0
    return 0.0


def extract_signal_components(
    payload: dict[str, Any],
    policy: PolicySnapshot,
) -> dict[str, float] | None:
    signal = _resolve_signal_blob(payload)
    raw = _extract_raw(payload, signal)

    if policy.panel_kind == "accum_signal_flags" or policy.score_kind in (
        "flag_penalty_adjusted",
        "classification_band",
    ):
        if raw is None:
            return None
        found: dict[str, float] = {"production_raw_score": raw}
        for c in policy.components:
            if c.key in ("production_raw_score", "strong_min", "moderate_min"):
                continue
            found[c.key] = _flag_fires(payload, signal, c.key, c.aliases)
        return found

    groups = _group_scores(payload, signal)
    # Alias production flow_confirmation ← institutional_flow common on captures
    if "institutional_flow" in groups and "flow_confirmation" not in groups:
        groups["flow_confirmation"] = groups["institutional_flow"]

    if policy.score_kind == "evidence_group_weights":
        # Group-only score: require at least one enabled group present
        found_eg: dict[str, float] = {}
        if raw is not None:
            found_eg["production_raw_score"] = raw
        for c in policy.enabled_components():
            if c.key in groups:
                found_eg[c.key] = groups[c.key]
                continue
            for a in c.aliases:
                if a.lower() in groups:
                    found_eg[c.key] = groups[a.lower()]
                    break
        if not any(c.key in found_eg for c in policy.enabled_components()):
            return None
        return found_eg

    if raw is None:
        return None
    found = {"production_raw_score": raw}
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
            return [], notes + [
                "no accum signal rows with production score "
                "(window signal.assessment.score / raw_exact_score or signal.raw_score)"
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
            out.append(
                PanelRow(ticker=ticker, date=date, components=comps, excess=ex)
            )
        if dropped:
            notes.append(f"dropped {dropped} rows missing primary H={primary_horizon}")
        notes.append(
            f"signal_panel n={len(out)} policy={policy.policy_id} "
            f"panel_kind={policy.panel_kind}"
        )
        return out, notes
