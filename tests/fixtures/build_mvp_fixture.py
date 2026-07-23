"""Build a tiny MVP-shaped SQLite for unit tests (no ai-saham imports)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path


def build_mvp_fixture(path: Path, *, with_hard: bool = True, min_bars: int = 65) -> Path:
    """Create a small SQLite matching MVP hard tables (or empty shell)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        if not with_hard:
            conn.execute("CREATE TABLE placeholder (id INTEGER)")
            conn.commit()
            return path

        conn.executescript(
            """
            CREATE TABLE candles (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (ticker, date)
            );
            CREATE TABLE company_fundamentals (
                ticker TEXT NOT NULL,
                fetched_date TEXT NOT NULL,
                pe_ratio_ttm REAL,
                roe_ttm REAL,
                pbv REAL,
                dividend_yield REAL,
                market_cap_idr REAL,
                PRIMARY KEY (ticker, fetched_date)
            );
            CREATE TABLE stock_meta (
                ticker TEXT PRIMARY KEY,
                sector TEXT,
                sub_sector TEXT
            );
            CREATE TABLE broker_summaries (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                source TEXT,
                foreign_buy_value REAL,
                foreign_sell_value REAL,
                foreign_buy_lot REAL,
                foreign_sell_lot REAL,
                total_value REAL,
                total_lot REAL,
                PRIMARY KEY (ticker, date, source)
            );
            CREATE TABLE foreign_flow_points (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                source TEXT,
                net_val REAL,
                net_lot REAL,
                PRIMARY KEY (ticker, date, source)
            );
            CREATE TABLE shareholding_composition (
                ticker TEXT NOT NULL,
                fetched_date TEXT NOT NULL,
                institution_pct REAL,
                individual_pct REAL,
                top_holder_name TEXT,
                top_holder_pct REAL,
                PRIMARY KEY (ticker, fetched_date)
            );
            """
        )

        start = date(2024, 1, 2)
        tickers = ("BBCA", "BBRI", "IHSG")
        rows = []
        for t in tickers:
            px = 100.0 if t != "IHSG" else 7000.0
            for i in range(min_bars):
                d = (start + timedelta(days=i)).isoformat()
                rows.append((t, d, px, px + 1, px - 1, px + 0.5, 1_000_000.0))
                px += 0.1
        conn.executemany(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.executemany(
            "INSERT INTO company_fundamentals VALUES (?,?,?,?,?,?,?)",
            [
                ("BBCA", "2024-06-01", 20.0, 0.18, 3.0, 0.02, 1e15),
                ("BBRI", "2024-06-01", 12.0, 0.15, 2.0, 0.04, 8e14),
            ],
        )
        conn.executemany(
            "INSERT INTO stock_meta VALUES (?,?,?)",
            [
                ("BBCA", "Financials", "Banks"),
                ("BBRI", "Financials", "Banks"),
            ],
        )
        for t in ("BBCA", "BBRI"):
            for i in range(20):
                d = (start + timedelta(days=i)).isoformat()
                conn.execute(
                    "INSERT INTO broker_summaries VALUES (?,?,?,?,?,?,?,?,?)",
                    (t, d, "stockbit", 1e9, 8e8, 1000, 800, 2e9, 2000),
                )
                conn.execute(
                    "INSERT INTO foreign_flow_points VALUES (?,?,?,?,?)",
                    (t, d, "stockbit", 2e8, 200),
                )
        conn.execute(
            "INSERT INTO shareholding_composition VALUES (?,?,?,?,?,?)",
            ("BBCA", "2024-06-01", 60.0, 40.0, "Foo", 10.0),
        )
        conn.commit()
    finally:
        conn.close()
    return path
