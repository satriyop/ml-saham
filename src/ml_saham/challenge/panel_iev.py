"""IEV pre-open panel: official rank + features + same-session open→close excess.

Capture selection prefers the **NCP decision window** (``is_ncp_locked`` and/or
pre-open clock 08:45–09:00), not merely the largest batch of the day.

Challenger features use ``log_iev`` and ``iep`` separately. Do **not** form
``iev/iep - 1`` — IEV is volume-scale and IEP is price; that ratio is meaningless.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.types import ChallengeExecutionPolicy
from ml_saham.data.aisaham_read import connect, load_candles, table_exists

# IDX pre-open / NCP decision window (local exchange clock on collected_at).
# Continuous trading starts ~09:00; prefer captures strictly before that.
_NCP_HHMM_START = "08:45"
_NCP_HHMM_END = "09:00"  # exclusive


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _as_dict(row: Any, cols: list[str]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return {k: row[k] for k in row.keys()}
    if isinstance(row, dict):
        return row
    return {cols[i]: row[i] for i in range(len(cols))}


def _capture_hhmm(collected_at: str) -> str | None:
    """Extract HH:MM from ISO / SQLite datetime strings."""
    s = str(collected_at or "").strip().replace("T", " ")
    if " " in s:
        time_part = s.split(" ", 1)[1]
        if len(time_part) >= 5 and time_part[2] == ":":
            return time_part[:5]
    if len(s) >= 5 and s[2] == ":":
        return s[:5]
    return None


def _in_ncp_clock_window(collected_at: str) -> bool:
    hhmm = _capture_hhmm(collected_at)
    if hhmm is None:
        return False
    return _NCP_HHMM_START <= hhmm < _NCP_HHMM_END


def _batch_is_ncp_locked(items: list[dict[str, Any]]) -> bool:
    for it in items:
        try:
            if int(it.get("is_ncp_locked") or 0) == 1:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _batch_sort_key(cap: str, items: list[dict[str, Any]]) -> tuple:
    """Higher is better: NCP flag → pre-open clock → size → latest capture."""
    ncp = 1 if _batch_is_ncp_locked(items) else 0
    clock = 1 if _in_ncp_clock_window(cap) else 0
    return (ncp, clock, len(items), cap)


def _pick_history_batches(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Per date keep one capture batch — prefer NCP decision window.

    Priority (highest first):
    1. ``is_ncp_locked=1`` batch
    2. Else capture clock in [08:45, 09:00)
    3. Else largest batch (legacy fallback)
    Ties → latest ``collected_at``.
    """
    notes: list[str] = []
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_date[str(r["date"])].append(r)

    out: list[dict[str, Any]] = []
    multi = 0
    n_ncp = 0
    n_clock = 0
    n_fallback = 0
    n_post_open_fallback = 0
    for _date, items in sorted(by_date.items()):
        by_cap: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for it in items:
            cap = str(it.get("collected_at") or it.get("fetched_at") or "")
            by_cap[cap].append(it)
        if len(by_cap) > 1:
            multi += 1
        best_cap = max(by_cap.keys(), key=lambda c: _batch_sort_key(c, by_cap[c]))
        batch = by_cap[best_cap]
        if _batch_is_ncp_locked(batch):
            n_ncp += 1
        elif _in_ncp_clock_window(best_cap):
            n_clock += 1
        else:
            n_fallback += 1
            hhmm = _capture_hhmm(best_cap) or ""
            if hhmm >= _NCP_HHMM_END:
                n_post_open_fallback += 1
        seen: set[str] = set()
        for it in sorted(batch, key=lambda x: str(x.get("ticker") or "")):
            t = str(it.get("ticker") or "").upper()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(it)
    if multi:
        notes.append(
            f"iev history: {multi} dates had multiple captures; "
            "preferred NCP-locked / pre-open clock batch (not merely largest)"
        )
    notes.append(
        f"iev batch_pick ncp_locked_days={n_ncp} preopen_clock_days={n_clock} "
        f"fallback_days={n_fallback} post_open_fallback_days={n_post_open_fallback}"
    )
    return out, notes


def _prefer_ncp_snapshot_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """For point table iev_snapshots: prefer is_ncp_locked=1 per (date,ticker)."""
    notes: list[str] = []
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        t = str(r.get("ticker") or "").upper()
        d = str(r.get("date") or "")
        if t and d:
            by_key[(d, t)].append(r)
    out: list[dict[str, Any]] = []
    used_ncp = 0
    for (_d, _t), items in by_key.items():
        ncp = [i for i in items if int(i.get("is_ncp_locked") or 0) == 1]
        chosen = ncp if ncp else items
        if ncp:
            used_ncp += 1
        # latest fetch if multiple
        chosen = sorted(
            chosen,
            key=lambda x: str(x.get("fetched_at") or x.get("collected_at") or ""),
        )
        out.append(chosen[-1])
    if used_ncp:
        notes.append(f"iev_snapshots preferred is_ncp_locked rows n={used_ncp}")
    return out, notes


def load_iev_raw_rows(
    conn: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Prefer iev_snapshot_history; fallback iev_snapshots."""
    notes: list[str] = []
    if table_exists(conn, "iev_snapshot_history"):
        cols_set = {
            r[1]
            for r in conn.execute("PRAGMA table_info(iev_snapshot_history)").fetchall()
        }
        want = ["date", "ticker", "iev", "rank", "iep"]
        if "collected_at" in cols_set:
            want.append("collected_at")
        elif "fetched_at" in cols_set:
            want.append("fetched_at")
        if "is_ncp_locked" in cols_set:
            want.append("is_ncp_locked")
        n = conn.execute("SELECT COUNT(*) AS n FROM iev_snapshot_history").fetchone()
        count = int(n["n"] if isinstance(n, sqlite3.Row) else n[0]) if n else 0
        if count > 0:
            select = ", ".join(want)
            raw = [
                _as_dict(r, want)
                for r in conn.execute(
                    f"SELECT {select} FROM iev_snapshot_history ORDER BY date, ticker"
                )
            ]
            notes.append(f"iev source=iev_snapshot_history n={len(raw)}")
            picked, batch_notes = _pick_history_batches(raw)
            notes.extend(batch_notes)
            return picked, notes

    if not table_exists(conn, "iev_snapshots"):
        return [], ["iev_snapshots and iev_snapshot_history missing"]

    cols_set = {
        r[1] for r in conn.execute("PRAGMA table_info(iev_snapshots)").fetchall()
    }
    want = ["date", "ticker", "iev", "rank", "iep"]
    if "fetched_at" in cols_set:
        want.append("fetched_at")
    if "is_ncp_locked" in cols_set:
        want.append("is_ncp_locked")
    select = ", ".join(want)
    raw = [
        _as_dict(r, want)
        for r in conn.execute(
            f"SELECT {select} FROM iev_snapshots ORDER BY date, ticker"
        )
    ]
    notes.append(f"iev source=iev_snapshots n={len(raw)}")
    return _prefer_ncp_snapshot_rows(raw)


def _open_close_excess(
    conn: sqlite3.Connection,
    pairs: list[tuple[str, str]],
) -> tuple[dict[tuple[str, str], float], list[str]]:
    """(ticker, date) -> open→close excess vs IHSG same day."""
    notes: list[str] = []
    if not pairs:
        return {}, notes
    tickers = sorted({t for t, _ in pairs} | {"IHSG"})
    candles = load_candles(conn, tickers)
    oc: dict[tuple[str, str], tuple[float, float]] = {}
    for c in candles:
        t = str(c["ticker"]).upper()
        d = str(c["date"])
        o = _f(c.get("open"))
        cl = _f(c.get("close"))
        if o > 0 and cl > 0:
            oc[(t, d)] = (o, cl)

    ihsg_ret: dict[str, float] = {}
    for (t, d), (o, cl) in oc.items():
        if t == "IHSG":
            ihsg_ret[d] = cl / o - 1.0

    out: dict[tuple[str, str], float] = {}
    missing_candle = 0
    missing_ihsg = 0
    for t, d in pairs:
        if (t, d) not in oc:
            missing_candle += 1
            continue
        if d not in ihsg_ret:
            missing_ihsg += 1
            continue
        o, cl = oc[(t, d)]
        stock_ret = cl / o - 1.0
        out[(t, d)] = stock_ret - ihsg_ret[d]
    if missing_candle:
        notes.append(f"dropped {missing_candle} rows missing open/close candles")
    if missing_ihsg:
        notes.append(f"dropped {missing_ihsg} rows missing IHSG open/close that date")
    return out, notes


def _component_features(
    iev: float, iep: float, rank: int, max_rank: int
) -> dict[str, float]:
    """Production rank score + scale-sane challenger features (no IEV/IEP ratio)."""
    return {
        "official_rank_score": float(max_rank - rank + 1),
        "iev": iev,
        "iep": iep,
        # log1p volume scale for ridge/equal-z (IEV is share volume, not price)
        "log_iev": math.log1p(max(iev, 0.0)),
    }


def build_iev_panel(
    db_path: Path | str,
    policy: ChallengeExecutionPolicy,
    *,
    primary_horizon: int = 0,
) -> tuple[list[PanelRow], list[str]]:
    """Labeled IEV rank panel; excess key = primary_horizon (0 for same-session)."""
    del policy  # policy weights unused for feature extraction; components fixed
    notes: list[str] = []
    path = Path(db_path)
    with connect(path) as conn:
        raw, src_notes = load_iev_raw_rows(conn)
        notes.extend(src_notes)
        if not raw:
            return [], notes + ["no IEV snapshot rows"]

        by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in raw:
            by_date[str(r["date"])].append(r)

        pairs: list[tuple[str, str]] = []
        staged: list[tuple[str, str, dict[str, float]]] = []
        for date, items in sorted(by_date.items()):
            ranks: list[int] = []
            for it in items:
                try:
                    ranks.append(int(it.get("rank") or 0))
                except (TypeError, ValueError):
                    ranks.append(0)
            max_rank = max(ranks) if ranks else 1
            max_rank = max(max_rank, 1)
            for it in items:
                t = str(it.get("ticker") or "").upper()
                if not t or t == "IHSG":
                    continue
                try:
                    rank = int(it.get("rank") or max_rank)
                except (TypeError, ValueError):
                    rank = max_rank
                iev = _f(it.get("iev"))
                iep = _f(it.get("iep"))
                comps = _component_features(iev, iep, rank, max_rank)
                staged.append((t, date, comps))
                pairs.append((t, date))

        excess_map, lab_notes = _open_close_excess(conn, pairs)
        notes.extend(lab_notes)

        rows: list[PanelRow] = []
        for t, date, comps in staged:
            if (t, date) not in excess_map:
                continue
            rows.append(
                PanelRow(
                    ticker=t,
                    date=date,
                    components=comps,
                    excess={primary_horizon: excess_map[(t, date)]},
                )
            )
        rows.sort(key=lambda r: (r.date, r.ticker))
        n_dates = len({r.date for r in rows})
        n_tickers = len({r.ticker for r in rows})
        notes.append(
            f"panel_rows={len(rows)} unique_tickers={n_tickers} n_dates={n_dates}"
        )
        if n_dates < 5:
            notes.append(f"thin IEV calendar: only {n_dates} labeled dates")
        return rows, notes
