"""Pre-open observation panel: PRE_OPEN_AUCTION_DIRECTION + open-path labels."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.panel_iev import _open_close_excess
from ml_saham.challenge.types import PolicySnapshot
from ml_saham.data.aisaham_read import connect, table_exists

PRE_OPEN_PURPOSE = "PRE_OPEN_AUCTION_DIRECTION"
MIN_FEATURES_PRESENT = 3

# payload key / alias → canonical component key (excluding production_raw_score)
_FEATURE_SOURCES: dict[str, str] = {
    "book_pressure": "book_pressure",
    "bid_offer_imbalance": "book_pressure",
    "delta_iev_ratio": "delta_iev_ratio",
    "delta_iev": "delta_iev_ratio",  # last resort if ratio absent; value still numeric
    "iep_gap_pct": "iep_gap_pct",
    "iev_intensity": "iev_intensity",
    "spread_pct": "spread_pct",
    "opening_broker_backing_score": "opening_broker_backing_score",
    "opening_broker_backing": "opening_broker_backing_score",
    "fvwap_discount_pct": "fvwap_discount_pct",
    "fvwap_discount": "fvwap_discount_pct",
}


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _trim_date(raw: str) -> str:
    d = str(raw or "").strip()
    if "T" in d:
        d = d.split("T", 1)[0]
    if " " in d:
        d = d.split(" ", 1)[0]
    return d


def extract_pre_open_components(
    payload: dict[str, Any],
    policy: PolicySnapshot,
) -> dict[str, float] | None:
    """Extract production_raw_score + feature components; None if row unusable."""
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    cand = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    factors = signal.get("factors") if isinstance(signal.get("factors"), dict) else {}

    raw = _f(signal.get("raw_score"))
    if raw is None:
        raw = _f(signal.get("score"))
    if raw is None:
        return None

    feature_set = set(policy.feature_keys())
    found: dict[str, float] = {"production_raw_score": raw}

    def ingest(src: dict[str, Any], *, allow_delta_iev_fallback: bool) -> None:
        for k, v in src.items():
            kl = str(k).lower()
            if kl == "delta_iev" and not allow_delta_iev_fallback:
                continue
            if kl == "delta_iev" and "delta_iev_ratio" in found:
                continue
            canon = _FEATURE_SOURCES.get(kl)
            if canon is None or canon not in feature_set:
                continue
            num = _f(v)
            if num is None:
                continue
            # ratio key always wins over prior delta_iev stand-in
            if kl == "delta_iev_ratio" or canon not in found:
                found[canon] = num

    # Prefer factors, then candidate; allow delta_iev only if ratio never seen
    ingest(factors, allow_delta_iev_fallback=False)
    if "delta_iev_ratio" not in found:
        # second pass factors for delta_iev only
        num = _f(factors.get("delta_iev"))
        if num is not None and "delta_iev_ratio" in feature_set:
            found["delta_iev_ratio"] = num
    ingest(cand, allow_delta_iev_fallback="delta_iev_ratio" not in found)

    present = sum(1 for k in feature_set if k in found)
    if present < MIN_FEATURES_PRESENT:
        return None

    for k in feature_set:
        found.setdefault(k, 0.0)
    return found


def _pct_to_return(x: float) -> float:
    """open_to_close_return_pct in live data is percent points (e.g. -1.33 → -0.0133)."""
    if abs(x) > 1.0:
        return x / 100.0
    # already a fraction, or tiny percent — treat as fraction if |x|<=1
    return x


def _load_outcome_returns(
    conn: sqlite3.Connection,
) -> dict[str, float]:
    """observation_id -> open_to_close return (fraction)."""
    if not table_exists(conn, "learning_outcome_labels"):
        return {}
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(learning_outcome_labels)").fetchall()
    }
    if "observation_id" not in cols or "metrics_json" not in cols:
        return {}
    sql = (
        "SELECT observation_id, metrics_json, availability, contract_id "
        "FROM learning_outcome_labels "
        "WHERE contract_id LIKE '%open_30m%' OR contract_id LIKE '%open%'"
    )
    out: dict[str, float] = {}
    for row in conn.execute(sql):
        if isinstance(row, sqlite3.Row):
            oid, metrics_json, avail, _cid = (
                row["observation_id"],
                row["metrics_json"],
                row["availability"],
                row["contract_id"],
            )
        else:
            oid, metrics_json, avail, _cid = row[0], row[1], row[2], row[3]
        if avail is not None and str(avail).upper() not in ("AVAILABLE", ""):
            continue
        try:
            metrics = json.loads(metrics_json or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(metrics, dict):
            continue
        raw = metrics.get("open_to_close_return_pct")
        num = _f(raw)
        if num is None:
            continue
        out[str(oid)] = _pct_to_return(num)
    return out


def build_pre_open_obs_panel(
    db_path: Path | str,
    policy: PolicySnapshot,
    *,
    primary_horizon: int = 0,
) -> tuple[list[PanelRow], list[str]]:
    """Labeled panel from PRE_OPEN observations."""
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            return [], ["learning_observations missing"]

        cols = {
            r[1] for r in conn.execute("PRAGMA table_info(learning_observations)").fetchall()
        }
        if "decision_payload_json" not in cols:
            return [], ["learning_observations.decision_payload_json missing"]

        has_oid = "observation_id" in cols
        select = "purpose, captured_at, decision_payload_json"
        if has_oid:
            select = "observation_id, " + select

        rows_db = conn.execute(
            f"SELECT {select} FROM learning_observations "
            f"WHERE purpose = ? ORDER BY captured_at ASC",
            (PRE_OPEN_PURPOSE,),
        ).fetchall()
        if not rows_db:
            rows_db = conn.execute(
                f"SELECT {select} FROM learning_observations "
                "WHERE purpose LIKE '%PRE_OPEN%' OR purpose LIKE '%pre_open%' "
                "ORDER BY captured_at ASC"
            ).fetchall()
        if not rows_db:
            return [], [
                "no PRE_OPEN_AUCTION_DIRECTION observations "
                "(run ai-saham pre-open captures to densify)"
            ]

        outcome_rets = _load_outcome_returns(conn) if has_oid else {}
        if outcome_rets:
            notes.append(f"outcome_open_30m labels available n={len(outcome_rets)}")

        # parse → (ticker, date, comps, cap, oid)
        staged: list[tuple[str, str, dict[str, float], str, str | None]] = []
        skipped = 0
        for row in rows_db:
            if isinstance(row, sqlite3.Row):
                keys = row.keys()
                oid = str(row["observation_id"]) if "observation_id" in keys else None
                purpose = row["purpose"]
                captured_at = row["captured_at"]
                payload_json = row["decision_payload_json"]
            else:
                if has_oid:
                    oid, purpose, captured_at, payload_json = (
                        str(row[0]),
                        row[1],
                        row[2],
                        row[3],
                    )
                else:
                    oid = None
                    purpose, captured_at, payload_json = row[0], row[1], row[2]
            del purpose
            try:
                payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                skipped += 1
                continue
            if not isinstance(payload, dict):
                skipped += 1
                continue
            ticker = str(payload.get("ticker") or "").upper()
            date = _trim_date(
                str(
                    payload.get("snapshot_date")
                    or payload.get("session_date")
                    or payload.get("decision_at")
                    or captured_at
                    or ""
                )
            )
            if not ticker or not date:
                skipped += 1
                continue
            comps = extract_pre_open_components(payload, policy)
            if not comps:
                skipped += 1
                continue
            staged.append((ticker, date, comps, str(captured_at or ""), oid))

        if skipped:
            notes.append(f"skipped {skipped} PRE_OPEN rows (empty signal/features)")

        # dedupe (ticker, date) last wins
        by_key: dict[tuple[str, str], tuple[dict[str, float], str, str | None]] = {}
        for ticker, date, comps, cap, oid in staged:
            by_key[(ticker, date)] = (comps, cap, oid)

        pairs = list(by_key.keys())
        candle_excess, lab_notes = _open_close_excess(conn, pairs)
        notes.extend(lab_notes)

        from ml_saham.data.aisaham_read import load_candles

        ihsg_oc: dict[str, float] = {}
        for c in load_candles(conn, ["IHSG"]):
            o = _f(c.get("open"))
            cl = _f(c.get("close"))
            d = str(c["date"])
            if o is not None and cl is not None and o > 0:
                ihsg_oc[d] = cl / o - 1.0

        n_outcome = 0
        n_candle = 0
        rows: list[PanelRow] = []
        dropped_label = 0
        for (ticker, date), (comps, _cap, oid) in sorted(by_key.items()):
            label: float | None = None
            if oid and oid in outcome_rets:
                gross = outcome_rets[oid]
                label = gross - ihsg_oc[date] if date in ihsg_oc else gross
                n_outcome += 1
            if label is None and (ticker, date) in candle_excess:
                label = candle_excess[(ticker, date)]
                n_candle += 1
            if label is None:
                dropped_label += 1
                continue
            rows.append(
                PanelRow(
                    ticker=ticker,
                    date=date,
                    components=comps,
                    excess={primary_horizon: label},
                )
            )

        if dropped_label:
            notes.append(f"dropped {dropped_label} rows missing open-path label")
        notes.append(
            f"label_source outcome_rows={n_outcome} candle_excess_rows={n_candle}"
        )
        notes.append(
            f"panel_rows={len(rows)} unique_tickers={len({r.ticker for r in rows})} "
            f"n_dates={len({r.date for r in rows})}"
        )
        if len(rows) < 5:
            notes.append(
                "thin PRE_OPEN panel — densify with ai-saham pre-open captures before decision use"
            )
        return rows, notes
