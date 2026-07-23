"""Read-only helpers against ai-saham SQLite schema (no ai-saham Python imports)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def connect(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"DB tidak ditemukan: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, name: str) -> set[str]:
    if not table_exists(conn, name):
        return set()
    rows = conn.execute(f"PRAGMA table_info({name})").fetchall()
    return {r["name"] for r in rows}


def _placeholders(n: int) -> str:
    return ",".join("?" * n)


def list_candle_tickers(conn: sqlite3.Connection) -> list[str]:
    if not table_exists(conn, "candles"):
        return []
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
    ).fetchall()
    return [r["ticker"] for r in rows]


def candle_date_range(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    if not table_exists(conn, "candles"):
        return None, None
    row = conn.execute("SELECT MIN(date), MAX(date) FROM candles").fetchone()
    return (row[0], row[1]) if row else (None, None)


def ticker_candle_count(conn: sqlite3.Connection, ticker: str) -> int:
    if not table_exists(conn, "candles"):
        return 0
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM candles WHERE ticker=?",
        (ticker,),
    ).fetchone()
    return int(row["n"]) if row else 0


def has_ihsg(conn: sqlite3.Connection) -> bool:
    return ticker_candle_count(conn, "IHSG") > 0


def load_candles(
    conn: sqlite3.Connection,
    tickers: Sequence[str] | None = None,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "candles"):
        return []
    sql = "SELECT ticker, date, open, high, low, close, volume FROM candles WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY ticker, date"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_latest_fundamentals(
    conn: sqlite3.Connection,
    tickers: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Latest row per ticker by fetched_date."""
    if not table_exists(conn, "company_fundamentals"):
        return []
    cols = table_columns(conn, "company_fundamentals")
    wanted = [
        "ticker",
        "fetched_date",
        "pe_ratio_ttm",
        "roe_ttm",
        "pbv",
        "dividend_yield",
        "market_cap_idr",
    ]
    select = ", ".join(c for c in wanted if c in cols)
    if "ticker" not in cols or "fetched_date" not in cols:
        return []
    sql = f"""
        SELECT {select} FROM company_fundamentals f
        WHERE fetched_date = (
            SELECT MAX(f2.fetched_date) FROM company_fundamentals f2
            WHERE f2.ticker = f.ticker
        )
    """
    params: list[Any] = []
    if tickers:
        sql += f" AND f.ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY f.ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_broker_summaries(
    conn: sqlite3.Connection,
    tickers: Sequence[str] | None = None,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "broker_summaries"):
        return []
    sql = """
        SELECT ticker, date, source,
               foreign_buy_value, foreign_sell_value,
               foreign_buy_lot, foreign_sell_lot, total_value, total_lot
        FROM broker_summaries WHERE 1=1
    """
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY ticker, date"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def broker_summaries_date_range(
    conn: sqlite3.Connection,
) -> tuple[str | None, str | None]:
    if not table_exists(conn, "broker_summaries"):
        return None, None
    row = conn.execute(
        "SELECT MIN(date), MAX(date) FROM broker_summaries"
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def load_foreign_flow_points(
    conn: sqlite3.Connection,
    tickers: Sequence[str] | None = None,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "foreign_flow_points"):
        return []
    sql = """
        SELECT ticker, date, source, net_val, net_lot
        FROM foreign_flow_points WHERE 1=1
    """
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " ORDER BY ticker, date"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_shareholding_latest(
    conn: sqlite3.Connection,
    tickers: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "shareholding_composition"):
        return []
    sql = """
        SELECT ticker, fetched_date, institution_pct, individual_pct,
               top_holder_name, top_holder_pct
        FROM shareholding_composition s
        WHERE fetched_date = (
            SELECT MAX(s2.fetched_date) FROM shareholding_composition s2
            WHERE s2.ticker = s.ticker
        )
    """
    params: list[Any] = []
    if tickers:
        sql += f" AND s.ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY s.ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"]) if row else 0


def distinct_ticker_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    cols = table_columns(conn, table)
    if "ticker" not in cols:
        return 0
    row = conn.execute(
        f"SELECT COUNT(DISTINCT ticker) AS n FROM {table}"
    ).fetchone()
    return int(row["n"]) if row else 0


def filter_tickers_with_min_bars(
    conn: sqlite3.Connection,
    tickers: Iterable[str],
    *,
    min_bars: int = 60,
) -> list[str]:
    """Keep tickers that have at least min_bars candle rows."""
    out: list[str] = []
    for t in tickers:
        if ticker_candle_count(conn, t) >= min_bars:
            out.append(t)
    return out
