"""Default liquid universe (LQ45-like) ∩ tickers present in DB."""

from __future__ import annotations

import sqlite3

from ml_saham.data.aisaham_read import filter_tickers_with_min_bars, list_candle_tickers

# Static LQ45-style liquid names for learning demos (not a live official list).
# Intersected with whatever is actually cached in candles.
LQ45_LIKE: tuple[str, ...] = (
    "ADRO",
    "AMRT",
    "ANTM",
    "ARTO",
    "ASII",
    "BBCA",
    "BBNI",
    "BBRI",
    "BBTN",
    "BMRI",
    "BRIS",
    "BRPT",
    "BUKA",
    "CPIN",
    "EMTK",
    "EXCL",
    "GGRM",
    "GOTO",
    "HRUM",
    "ICBP",
    "INCO",
    "INDF",
    "INKP",
    "INTP",
    "ITMG",
    "JPFA",
    "KLBF",
    "MDKA",
    "MEDC",
    "MTEL",
    "PGAS",
    "PTBA",
    "SCMA",
    "SMGR",
    "TBIG",
    "TLKM",
    "TOWR",
    "UNTR",
    "UNVR",
    "ACES",
    "AKRA",
    "BSDE",
    "CTRA",
    "ERAA",
    "HMSP",
    "ISAT",
    "JSMR",
    "MAPA",
    "MNCN",
    "PWON",
    "SMRA",
    "TPIA",
)


def default_universe(
    conn: sqlite3.Connection,
    *,
    min_bars: int = 60,
    candidates: tuple[str, ...] | None = None,
) -> list[str]:
    """LQ45-like ∩ candles tickers with enough history (excludes IHSG)."""
    pool = candidates if candidates is not None else LQ45_LIKE
    cached = set(list_candle_tickers(conn))
    cached.discard("IHSG")
    intersect = [t for t in pool if t in cached]
    return filter_tickers_with_min_bars(conn, intersect, min_bars=min_bars)
