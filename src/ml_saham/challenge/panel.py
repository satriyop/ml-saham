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

ACCUM_PURPOSES = (
    "ACCUMULATION_DISCOVERY",
    "ACCUM_PATH",
    "accum_10d",
)


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


def extract_components(payload: dict[str, Any], policy: PolicySnapshot) -> dict[str, float] | None:
    """Adaptive extract of component points from observation payload."""
    aliases = _alias_lookup(policy)
    found: dict[str, float] = {}

    # 1) flow_signals list: [{key, score, weight}, ...]
    signal = payload.get("signal") or {}
    flow_ev = signal.get("flow_evidence") or {}
    for item in flow_ev.get("flow_signals") or []:
        if not isinstance(item, dict):
            continue
        k = str(item.get("key") or "").lower()
        if k not in aliases:
            continue
        try:
            found[aliases[k]] = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            continue

    # 2) sub_signal_fingerprint numeric fields
    fp = payload.get("sub_signal_fingerprint") or {}
    fp_map = {
        "rsi_at_signal": "rsi_headroom",
        "vwap_position_at_signal": "vwap_discount",
        "bb_width_pctile_at_signal": "bb_squeeze",
        "ia_foreign_participation": "foreign_flow_ratio",
        "foreign_concentration_at_signal": "consistency",
    }
    for src, dest in fp_map.items():
        if dest in found:
            continue
        if src in fp and isinstance(fp[src], (int, float)):
            # scale raw-ish values into 0..weight space roughly
            w = next((c.weight for c in policy.components if c.key == dest), 10.0)
            val = float(fp[src])
            if dest == "rsi_headroom":
                # map RSI 25-75 into points
                score = max(0.0, min(1.0, (val - 25.0) / 50.0)) * w
            elif dest == "vwap_discount":
                score = max(0.0, min(1.0, abs(val) * 10)) * w
            elif dest == "bb_squeeze":
                score = max(0.0, min(1.0, 1.0 - val)) * w
            else:
                score = max(0.0, min(1.0, abs(val))) * w
            found[dest] = score

    # 3) features_by_window (prefer longest lookback if present)
    fbw = payload.get("features_by_window") or payload.get("features") or {}
    if isinstance(fbw, dict):
        # pick one window dict
        window_dicts = [v for v in fbw.values() if isinstance(v, dict)] if fbw else []
        if not window_dicts and all(not isinstance(v, dict) for v in fbw.values()):
            window_dicts = [fbw]
        for wd in reversed(window_dicts):
            for k, v in wd.items():
                kl = str(k).lower()
                canon = aliases.get(kl)
                if canon and canon not in found and isinstance(v, (int, float)):
                    found[canon] = float(v)

    # Require at least 3 enabled components
    enabled_keys = {c.key for c in policy.enabled_components()}
    present = enabled_keys & set(found)
    if len(present) < 3:
        return None
    # fill missing enabled with 0 for scorer stability only if we have majority
    for k in enabled_keys:
        found.setdefault(k, 0.0)
    return {k: found[k] for k in enabled_keys}


def load_observation_rows(
    conn: sqlite3.Connection,
    policy: PolicySnapshot,
) -> list[tuple[str, str, dict[str, float], str]]:
    """Return list of (ticker, date, components, captured_at)."""
    if not table_exists(conn, "learning_observations"):
        return []
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(learning_observations)").fetchall()
    }
    if "decision_payload_json" not in cols:
        return []
    purpose_filter = ",".join("?" * len(ACCUM_PURPOSES))
    sql = (
        f"SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
        f"WHERE purpose IN ({purpose_filter}) ORDER BY captured_at ASC"
    )
    # also accept any purpose containing ACCUM if empty
    rows = conn.execute(sql, ACCUM_PURPOSES).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT purpose, captured_at, decision_payload_json FROM learning_observations "
            "WHERE purpose LIKE '%ACCUM%' OR purpose LIKE '%accum%' "
            "ORDER BY captured_at ASC"
        ).fetchall()

    out: list[tuple[str, str, dict[str, float], str]] = []
    for purpose, captured_at, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        ticker = str(payload.get("ticker") or "").upper()
        date = str(
            payload.get("snapshot_date")
            or payload.get("as_of")
            or payload.get("date")
            or ""
        )
        if not ticker or not date:
            continue
        comps = extract_components(payload, policy)
        if not comps:
            continue
        out.append((ticker, date, comps, str(captured_at or "")))
    return out


def build_panel(
    db_path: Path | str,
    policy: PolicySnapshot,
    horizons: tuple[int, ...],
    primary_horizon: int,
) -> tuple[list[PanelRow], list[str]]:
    """Build labeled panel; notes collect non-fatal warnings."""
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        raw = load_observation_rows(conn, policy)
        if not raw:
            return [], ["no extractable accum observations with components"]

        # dedupe (ticker, date) keep last by captured_at order
        by_key: dict[tuple[str, str], tuple[dict[str, float], str]] = {}
        for ticker, date, comps, cap in raw:
            by_key[(ticker, date)] = (comps, cap)
        tickers = sorted({t for t, _ in by_key})
        excess_map = build_forward_excess(conn, tickers, horizons)
        if not excess_map:
            return [], ["could not build IHSG-aligned forward excess (check IHSG candles)"]

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
