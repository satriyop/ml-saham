"""Shared panel helpers for MVP demos (Direct mode on ai-saham SQLite)."""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from datetime import date
from typing import Any

from ml_saham.data.aisaham_read import (
    connect,
    load_broker_summaries,
    load_candles,
    load_foreign_flow_points,
    load_latest_fundamentals,
    load_shareholding_latest,
)
from ml_saham.data.universe import default_universe
from ml_saham.eval.costs import apply_haircut


def today_iso() -> str:
    return date.today().isoformat()


def zscore(values: list[float | None]) -> list[float | None]:
    xs = [v for v in values if v is not None and not math.isnan(float(v))]
    if len(xs) < 2:
        return [None for _ in values]
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    std = math.sqrt(var) if var > 0 else 0.0
    if std == 0.0:
        return [0.0 if v is not None else None for v in values]
    out: list[float | None] = []
    for v in values:
        if v is None or math.isnan(float(v)):
            out.append(None)
        else:
            out.append((float(v) - mean) / std)
    return out


def forward_returns_by_ticker(
    conn: sqlite3.Connection,
    tickers: list[str],
    *,
    as_of: str,
    horizon: int = 5,
) -> dict[str, float]:
    """Simple forward return from as_of close to close ~horizon sessions later."""
    candles = load_candles(conn, tickers)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))
    out: dict[str, float] = {}
    for t, series in by_t.items():
        series.sort(key=lambda x: x[0])
        dates = [d for d, _ in series]
        if as_of not in dates:
            # nearest on or before as_of
            idxs = [i for i, d in enumerate(dates) if d <= as_of]
            if not idxs:
                continue
            i0 = idxs[-1]
        else:
            i0 = dates.index(as_of)
        i1 = i0 + horizon
        if i1 >= len(series):
            continue
        c0 = series[i0][1]
        c1 = series[i1][1]
        if c0 == 0:
            continue
        out[t] = (c1 / c0) - 1.0
    return out


def ihsg_forward_return(
    conn: sqlite3.Connection,
    *,
    as_of: str,
    horizon: int = 5,
) -> float | None:
    m = forward_returns_by_ticker(conn, ["IHSG"], as_of=as_of, horizon=horizon)
    return m.get("IHSG")


def pick_as_of(conn: sqlite3.Connection, tickers: list[str], *, min_forward: int = 5) -> str | None:
    """Pick a recent as_of that still has forward bars for most names."""
    candles = load_candles(conn, tickers + ["IHSG"])
    if not candles:
        return None
    by_date: dict[str, set[str]] = defaultdict(set)
    all_dates: set[str] = set()
    for row in candles:
        by_date[row["date"]].add(row["ticker"])
        all_dates.add(row["date"])
    dates = sorted(all_dates)
    if len(dates) <= min_forward + 5:
        return dates[len(dates) // 2] if dates else None
    # choose date near the end but leave horizon room
    target = dates[-(min_forward + 3)]
    return target


def resolve_universe(conn: sqlite3.Connection, *, limit: int | None = 40) -> list[str]:
    uni = default_universe(conn, min_bars=40)
    if limit is not None:
        return uni[:limit]
    return uni


def maybe_haircut(returns: list[float], *, with_costs: bool) -> list[float]:
    if with_costs:
        return apply_haircut(returns)
    return list(returns)


def load_fundie_map(conn: sqlite3.Connection, tickers: list[str]) -> dict[str, dict[str, Any]]:
    rows = load_latest_fundamentals(conn, tickers)
    return {r["ticker"]: dict(r) for r in rows}


def load_owner_map(conn: sqlite3.Connection, tickers: list[str]) -> dict[str, dict[str, Any]]:
    rows = load_shareholding_latest(conn, tickers)
    return {r["ticker"]: dict(r) for r in rows}


def foreign_net_nday(
    conn: sqlite3.Connection,
    tickers: list[str],
    *,
    as_of: str,
    window: int = 5,
) -> dict[str, float]:
    """Sum foreign buy-sell value over last `window` sessions ending at as_of."""
    # Prefer broker_summaries; fall back to foreign_flow_points
    rows = load_broker_summaries(conn, tickers)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    if rows:
        for r in rows:
            buy = float(r["foreign_buy_value"] or 0)
            sell = float(r["foreign_sell_value"] or 0)
            by_t[r["ticker"]].append((r["date"], buy - sell))
    else:
        for r in load_foreign_flow_points(conn, tickers):
            by_t[r["ticker"]].append((r["date"], float(r["net_val"] or 0)))

    out: dict[str, float] = {}
    for t, series in by_t.items():
        series.sort(key=lambda x: x[0])
        dates = [d for d, _ in series]
        if as_of not in dates:
            idxs = [i for i, d in enumerate(dates) if d <= as_of]
            if not idxs:
                continue
            end = idxs[-1]
        else:
            end = dates.index(as_of)
        start = max(0, end - window + 1)
        out[t] = sum(v for _, v in series[start : end + 1])
    return out


def momentum_nday(
    conn: sqlite3.Connection,
    tickers: list[str],
    *,
    as_of: str,
    window: int = 20,
) -> dict[str, float]:
    candles = load_candles(conn, tickers)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))
    out: dict[str, float] = {}
    for t, series in by_t.items():
        series.sort(key=lambda x: x[0])
        dates = [d for d, _ in series]
        if as_of not in dates:
            idxs = [i for i, d in enumerate(dates) if d <= as_of]
            if not idxs:
                continue
            end = idxs[-1]
        else:
            end = dates.index(as_of)
        start = end - window
        if start < 0:
            continue
        c0 = series[start][1]
        c1 = series[end][1]
        if c0 == 0:
            continue
        out[t] = (c1 / c0) - 1.0
    return out
