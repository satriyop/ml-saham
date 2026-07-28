"""Read-only helpers for phase-2 tables (earnings, corp, IEV, labels)."""

from __future__ import annotations

import sqlite3
from typing import Any

from ml_saham.data.aisaham_read import _placeholders, table_columns, table_exists


def load_earnings(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "earnings_cache"):
        return []
    cols = table_columns(conn, "earnings_cache")
    if not {"ticker", "year", "quarter"} <= cols:
        return []
    select = [
        c
        for c in (
            "ticker",
            "year",
            "quarter",
            "eps_actual",
            "eps_estimate",
            "eps_surprise_pct",
            "eps_yoy_change",
            "fetched_date",
        )
        if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM earnings_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker, year, quarter"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_corp_actions(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Prefer corp_action_cache; fall back to corporate_action_events."""
    if table_exists(conn, "corp_action_cache"):
        cols = table_columns(conn, "corp_action_cache")
        if "ticker" in cols:
            select = [
                c
                for c in (
                    "ticker",
                    "event_type",
                    "ex_date",
                    "cum_date",
                    "announcement_date",
                    "detail",
                    "fetched_date",
                )
                if c in cols
            ]
            sql = f"SELECT {', '.join(select)} FROM corp_action_cache WHERE 1=1"
            params: list[Any] = []
            if tickers:
                sql += f" AND ticker IN ({_placeholders(len(tickers))})"
                params.extend(tickers)
            sql += " ORDER BY ex_date, ticker"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    if table_exists(conn, "corporate_action_events"):
        cols = table_columns(conn, "corporate_action_events")
        if "ticker" not in cols:
            return []
        # join dates if available
        if table_exists(conn, "corporate_action_event_dates"):
            sql = """
                SELECT e.ticker, e.event_type, d.event_date AS ex_date, e.event_note AS detail
                FROM corporate_action_events e
                LEFT JOIN corporate_action_event_dates d
                  ON e.source=d.source AND e.event_type=d.event_type
                 AND e.source_event_id=d.source_event_id AND d.date_role='ex_date'
                WHERE 1=1
            """
            params = []
            if tickers:
                sql += f" AND e.ticker IN ({_placeholders(len(tickers))})"
                params.extend(tickers)
            sql += " ORDER BY ex_date, e.ticker"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
    return []


def load_iev_snapshots(
    conn: sqlite3.Connection,
    *,
    as_of: str | None = None,
    limit_dates: int = 5,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "iev_snapshots"):
        return []
    cols = table_columns(conn, "iev_snapshots")
    if not {"date", "ticker"} <= cols:
        return []
    select = [
        c for c in ("date", "ticker", "iev", "rank", "iep", "is_ncp_locked") if c in cols
    ]
    if as_of:
        sql = f"SELECT {', '.join(select)} FROM iev_snapshots WHERE date=? ORDER BY rank"
        return [dict(r) for r in conn.execute(sql, (as_of,)).fetchall()]
    dates = [
        r["date"]
        for r in conn.execute(
            "SELECT DISTINCT date FROM iev_snapshots ORDER BY date DESC LIMIT ?",
            (limit_dates,),
        ).fetchall()
    ]
    if not dates:
        return []
    ph = _placeholders(len(dates))
    sql = (
        f"SELECT {', '.join(select)} FROM iev_snapshots "
        f"WHERE date IN ({ph}) ORDER BY date DESC, rank"
    )
    return [dict(r) for r in conn.execute(sql, dates).fetchall()]


def load_forward_labels(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
    *,
    horizon: int = 5,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "signal_forward_labels"):
        return []
    cols = table_columns(conn, "signal_forward_labels")
    if not {"ticker", "signal_date"} <= cols:
        return []
    select = [
        c
        for c in (
            "ticker",
            "signal_date",
            "horizon",
            "close_return",
            "max_forward_return",
            "max_adverse_excursion",
        )
        if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM signal_forward_labels WHERE 1=1"
    params: list[Any] = []
    if "horizon" in cols:
        sql += " AND horizon=?"
        params.append(horizon)
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY signal_date DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_regime_observations(
    conn: sqlite3.Connection,
    *,
    limit: int = 120,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "regime_observations"):
        return []
    cols = table_columns(conn, "regime_observations")
    if "observation_date" not in cols:
        return []
    select = [
        c
        for c in (
            "observation_date",
            "regime",
            "regime_score",
            "regime_confidence",
            "forward_ihsg_return_5d",
            "forward_ihsg_return_10d",
        )
        if c in cols
    ]
    sql = (
        f"SELECT {', '.join(select)} FROM regime_observations "
        "ORDER BY observation_date DESC LIMIT ?"
    )
    return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]


def headline_table_name(conn: sqlite3.Connection) -> str | None:
    for name in ("headlines_cache", "news_headlines", "headline_cache"):
        if table_exists(conn, name):
            return name
    return None


def load_seasonality(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "seasonality_cache"):
        return []
    cols = table_columns(conn, "seasonality_cache")
    if not {"ticker", "month"} <= cols:
        return []
    select = [
        c for c in ("ticker", "year", "month", "avg_return_pct", "win_rate_pct", "positive_years", "total_years") if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM seasonality_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker, month"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_analysts(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "analyst_cache"):
        return []
    cols = table_columns(conn, "analyst_cache")
    if "ticker" not in cols:
        return []
    select = [
        c for c in ("ticker", "buy_count", "hold_count", "sell_count", "avg_price_target", "current_price", "fetched_date") if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM analyst_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_broker_distribution(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "broker_distribution_cache"):
        return []
    cols = table_columns(conn, "broker_distribution_cache")
    if not {"ticker", "trading_date"} <= cols:
        return []
    select = [
        c for c in ("ticker", "trading_date", "top_buyers_json", "top_sellers_json", "fetched_date") if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM broker_distribution_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY trading_date DESC, ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_shareholding(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "shareholding_composition"):
        return []
    cols = table_columns(conn, "shareholding_composition")
    if "ticker" not in cols:
        return []
    select = [
        c for c in ("ticker", "fetched_date", "report_date", "institution_pct", "individual_pct", "top_holder_name", "top_holder_pct") if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM shareholding_composition WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_company_financials(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "company_financials"):
        return []
    cols = table_columns(conn, "company_financials")
    if "ticker" not in cols:
        return []
    select = [
        c for c in (
            "ticker", "statement_kind", "period_end", "period_type", "total_revenue",
            "net_income", "operating_income", "total_assets", "total_liabilities",
            "stockholders_equity", "cash_and_equivalents", "total_debt", "operating_cash_flow",
            "free_cash_flow", "fetched_at"
        ) if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM company_financials WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker, period_end DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_bandar_detector(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "bandar_detector"):
        return []
    cols = table_columns(conn, "bandar_detector")
    if "ticker" not in cols:
        return []
    select = [
        c for c in (
            "ticker", "session_date", "broker_accdist", "today_accdist", "five_day_accdist",
            "top1_accdist", "top1_percent", "today_percent", "total_buyer", "total_seller",
            "top3_accdist", "top5_accdist", "top10_accdist", "number_broker_buysell",
            "vwap", "total_value", "total_volume"
        ) if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM bandar_detector WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY session_date DESC, ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_forward_estimates(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "forward_estimates_cache"):
        return []
    cols = table_columns(conn, "forward_estimates_cache")
    if "ticker" not in cols:
        return []
    select = [
        c for c in ("ticker", "fetched_date", "forward_eps_1y", "revenue_forward_1y", "current_price", "forward_pe") if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM forward_estimates_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_ticker_notations(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not table_exists(conn, "ticker_notation_cache"):
        return []
    cols = table_columns(conn, "ticker_notation_cache")
    if "ticker" not in cols:
        return []
    select = [
        c for c in (
            "ticker", "status", "tradeable", "listing_board", "sector", "sub_sector",
            "haircut_percentage", "notations_json", "market_status", "suspend_info",
            "corp_action_active", "has_uma", "fetched_date"
        ) if c in cols
    ]
    sql = f"SELECT {', '.join(select)} FROM ticker_notation_cache WHERE 1=1"
    params: list[Any] = []
    if tickers:
        sql += f" AND ticker IN ({_placeholders(len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY ticker"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]




