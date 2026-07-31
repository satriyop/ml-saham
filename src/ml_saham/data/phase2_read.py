"""Read-only helpers for phase-2 tables (earnings, corp, IEV, labels)."""

from __future__ import annotations

import json
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


def _metric_float(metrics: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        if k not in metrics:
            continue
        v = metrics[k]
        if v is None or isinstance(v, bool):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _load_forward_labels_from_corpus(
    conn: sqlite3.Connection,
    tickers: list[str] | None,
    *,
    horizon: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Canonical plane: learning_outcome_labels (+ optional join to observations)."""
    if not table_exists(conn, "learning_outcome_labels"):
        return []
    lol_cols = table_columns(conn, "learning_outcome_labels")
    if not {"observation_id", "metrics_json", "contract_id"} <= lol_cols:
        return []

    has_obs = table_exists(conn, "learning_observations")
    obs_cols = table_columns(conn, "learning_observations") if has_obs else set()
    has_payload = "decision_payload_json" in obs_cols
    has_oid = "observation_id" in obs_cols

    if has_obs and has_payload and has_oid:
        order = (
            "ORDER BY lol.labeled_at DESC "
            if "labeled_at" in lol_cols
            else ""
        )
        sql = (
            "SELECT lol.observation_id, lol.contract_id, lol.metrics_json, "
            "lol.availability, lo.decision_payload_json "
            "FROM learning_outcome_labels lol "
            "LEFT JOIN learning_observations lo "
            "ON lo.observation_id = lol.observation_id "
            f"{order}"
        )
    else:
        order = (
            "ORDER BY labeled_at DESC " if "labeled_at" in lol_cols else ""
        )
        sql = (
            "SELECT observation_id, contract_id, metrics_json, availability, NULL "
            f"FROM learning_outcome_labels {order}"
        )

    # Fetch a bit more then filter — horizon lives in metrics_json / contract
    fetch_limit = max(limit * 4, limit)
    sql_limited = f"{sql} LIMIT {int(fetch_limit)}"
    rows_raw = conn.execute(sql_limited).fetchall()

    ticker_set = {t.upper() for t in tickers} if tickers else None
    out: list[dict[str, Any]] = []
    for row in rows_raw:
        if isinstance(row, sqlite3.Row):
            oid = row[0]
            contract_id = row[1]
            metrics_json = row[2]
            avail = row[3]
            payload_json = row[4]
        else:
            oid, contract_id, metrics_json, avail, payload_json = row

        if avail is not None and str(avail).upper() not in ("AVAILABLE", ""):
            continue
        try:
            metrics = json.loads(metrics_json or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(metrics, dict):
            continue

        # Horizon filter: metrics.horizon preferred; else contract_id hint
        mh = metrics.get("horizon")
        try:
            mh_i = int(mh) if mh is not None else None
        except (TypeError, ValueError):
            mh_i = None
        if mh_i is not None and mh_i != horizon:
            continue
        if mh_i is None and contract_id:
            cid = str(contract_id).lower()
            # Map common contracts when metrics omit horizon
            if horizon == 10 and "accum_10d" not in cid and "accum_3d" not in cid:
                if "accum_20d" in cid or "open_30m" in cid:
                    continue
            if horizon == 5 and "accum_" in cid and "5" not in cid:
                # allow generic fixture contracts without strict match when metrics carry return
                if not any(
                    k in metrics
                    for k in ("close_return", "close_return_pct", "excess_return")
                ):
                    continue

        close_ret = _metric_float(
            metrics,
            "close_return",
            "close_return_pct",
            "excess_return",
            "excess_return_pct",
        )
        if close_ret is None:
            continue
        # percent points → fraction if clearly percent-scale
        if abs(close_ret) > 1.0 and "pct" in str(
            next(
                (
                    k
                    for k in (
                        "close_return_pct",
                        "excess_return_pct",
                        "close_return",
                        "excess_return",
                    )
                    if k in metrics
                ),
                "",
            )
        ):
            close_ret = close_ret / 100.0
        elif abs(close_ret) > 2.0:
            close_ret = close_ret / 100.0

        ticker = str(metrics.get("ticker") or "").upper()
        signal_date = str(
            metrics.get("signal_date")
            or metrics.get("session_date")
            or metrics.get("snapshot_date")
            or metrics.get("as_of")
            or ""
        )
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                payload = {}
            if isinstance(payload, dict):
                if not ticker:
                    ticker = str(payload.get("ticker") or "").upper()
                if not signal_date:
                    signal_date = str(
                        payload.get("session_date")
                        or payload.get("snapshot_date")
                        or payload.get("as_of")
                        or payload.get("date")
                        or ""
                    )
        if "T" in signal_date:
            signal_date = signal_date.split("T", 1)[0]
        if not ticker or not signal_date:
            continue
        if ticker_set is not None and ticker not in ticker_set:
            continue

        out.append(
            {
                "ticker": ticker,
                "signal_date": signal_date,
                "horizon": int(metrics.get("horizon") or horizon),
                "close_return": close_ret,
                "max_forward_return": _metric_float(
                    metrics, "max_forward_return", "max_forward_return_pct"
                ),
                "max_adverse_excursion": _metric_float(
                    metrics, "max_adverse_excursion", "max_adverse_excursion_pct"
                ),
                "observation_id": str(oid or ""),
                "contract_id": str(contract_id or ""),
                "label_source": "learning_outcome_labels",
            }
        )
        if len(out) >= limit:
            break
    return out


def _load_forward_labels_legacy(
    conn: sqlite3.Connection,
    tickers: list[str] | None,
    *,
    horizon: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Retired table name — soft fallback for old local fixtures only."""
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
    raw = conn.execute(sql, params).fetchall()
    rows: list[dict[str, Any]] = []
    for r in raw:
        if isinstance(r, sqlite3.Row):
            item = dict(r)
        else:
            item = {c: r[i] for i, c in enumerate(select)}
        item["label_source"] = "signal_forward_labels"
        rows.append(item)
    return rows


def load_forward_labels(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
    *,
    horizon: int = 5,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Curriculum helper: forward returns for walk-forward-style labs.

    **Canonical plane (live ai-saham):** ``learning_outcome_labels`` joined to
    ``learning_observations`` for ticker/date when needed.

    **Legacy (retired):** ``signal_forward_labels`` only if the corpus path is
    empty (old fixtures). Soft-empty when neither is usable.

    ADR-002 challenge evaluation labels remain protocol-owned from candles;
    this helper is not the challenge SSOT.
    """
    corpus = _load_forward_labels_from_corpus(
        conn, tickers, horizon=horizon, limit=limit
    )
    if corpus:
        return corpus
    return _load_forward_labels_legacy(conn, tickers, horizon=horizon, limit=limit)


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




