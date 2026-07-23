"""Build a tiny MVP-shaped SQLite for unit tests (no ai-saham imports)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

# Must intersect LQ45_LIKE in universe.py
_STOCKS = (
    "BBCA",
    "BBRI",
    "BMRI",
    "BBNI",
    "TLKM",
    "ASII",
    "UNVR",
    "ICBP",
    "KLBF",
    "INDF",
    "ADRO",
    "PTBA",
    "ANTM",
    "MDKA",
    "GOTO",
)


def build_mvp_fixture(path: Path, *, with_hard: bool = True, min_bars: int = 80) -> Path:
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
            CREATE TABLE insider_cache (
                ticker TEXT NOT NULL,
                name TEXT,
                role TEXT,
                action_type TEXT,
                shares REAL,
                price REAL,
                transaction_date TEXT,
                ownership_before_pct REAL,
                ownership_after_pct REAL,
                fetched_date TEXT
            );
            """
        )

        sectors = (
            "Financials",
            "Financials",
            "Financials",
            "Financials",
            "Communications",
            "Consumer Cyclical",
            "Consumer Defensive",
            "Consumer Defensive",
            "Healthcare",
            "Consumer Defensive",
            "Energy",
            "Energy",
            "Basic Materials",
            "Basic Materials",
            "Technology",
        )

        start = date(2024, 1, 2)
        candle_rows = []
        for si, t in enumerate((*_STOCKS, "IHSG")):
            px = 7000.0 if t == "IHSG" else 100.0 + si * 3.0
            drift = 0.15 if t == "IHSG" else 0.05 + (si % 5) * 0.03
            for i in range(min_bars):
                d = (start + timedelta(days=i)).isoformat()
                shock = 0.0
                if t != "IHSG" and i == 40 and si == 0:
                    shock = px * 0.12
                close = px + shock
                vol = 1_000_000.0 + si * 10_000 + (i % 7) * 1000
                # volume spike for Ch.8
                if t != "IHSG" and i == 55 and si == 1:
                    vol *= 25
                candle_rows.append(
                    (t, d, close - 1, close + 1, close - 2, close, vol)
                )
                px += drift
        conn.executemany(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
            candle_rows,
        )

        fundie_rows = []
        meta_rows = []
        share_rows = []
        insider_rows = []
        for si, t in enumerate(_STOCKS):
            pe = 8.0 + si * 1.5
            roe = 0.05 + (si % 6) * 0.03
            pbv = 1.0 + si * 0.2
            fundie_rows.append((t, "2024-06-01", pe, roe, pbv, 0.02, 1e14 * (si + 1)))
            meta_rows.append((t, sectors[si], "Sub"))
            share_rows.append((t, "2024-06-01", 40.0 + si, 60.0 - si, "Holder", 5.0))
            # usable insider + one absurd placeholder
            insider_rows.append(
                (
                    t,
                    "Name",
                    "Director",
                    "BUY" if si % 2 == 0 else "SELL",
                    100_000.0 * (si + 1),
                    100.0,
                    (start + timedelta(days=50 + si)).isoformat(),
                    1.0,
                    1.1,
                    "2024-06-01",
                )
            )
        insider_rows.append(
            (
                "BBCA",
                "__NONE__",
                "",
                "NONE",
                0,
                0.0,
                "1970-01-01",
                0.0,
                0.0,
                "2024-06-01",
            )
        )
        conn.executemany(
            "INSERT INTO company_fundamentals VALUES (?,?,?,?,?,?,?)",
            fundie_rows,
        )
        conn.executemany("INSERT INTO stock_meta VALUES (?,?,?)", meta_rows)
        conn.executemany(
            "INSERT INTO shareholding_composition VALUES (?,?,?,?,?,?)",
            share_rows,
        )
        conn.executemany(
            "INSERT INTO insider_cache VALUES (?,?,?,?,?,?,?,?,?,?)",
            insider_rows,
        )

        for si, t in enumerate(_STOCKS):
            for i in range(min_bars):
                d = (start + timedelta(days=i)).isoformat()
                buy = 1e9 + si * 1e7 + i * 1e5
                sell = 8e8 + (14 - si) * 1e7
                conn.execute(
                    "INSERT INTO broker_summaries VALUES (?,?,?,?,?,?,?,?,?)",
                    (t, d, "stockbit", buy, sell, 1000, 800, buy + sell, 1800),
                )
                conn.execute(
                    "INSERT INTO foreign_flow_points VALUES (?,?,?,?,?)",
                    (t, d, "stockbit", buy - sell, 200.0 + si),
                )
        conn.commit()
    finally:
        conn.close()
    return path
