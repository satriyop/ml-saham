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
                # volume spike for Ch.9 volume-anomaly
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

        # Phase-2 tables (minimal for doctor + demos)
        conn.executescript(
            """
            CREATE TABLE earnings_cache (
                ticker TEXT, year INT, quarter INT,
                eps_actual REAL, eps_estimate REAL, eps_surprise_pct REAL,
                eps_yoy_change REAL, fetched_date TEXT
            );
            CREATE TABLE corp_action_cache (
                ticker TEXT, event_type TEXT, ex_date TEXT, cum_date TEXT,
                announcement_date TEXT, detail TEXT, fetched_date TEXT
            );
            CREATE TABLE iev_snapshots (
                date TEXT, ticker TEXT, iev REAL, rank INT, iep REAL,
                fetched_at TEXT, is_ncp_locked INT
            );
            -- Fixture-only legacy table for curriculum walk_forward demos.
            -- Live ai-saham: learning_outcome_labels (not this name).
            CREATE TABLE signal_forward_labels (
                id INTEGER PRIMARY KEY,
                ticker TEXT, signal_date TEXT, horizon INT,
                close_return REAL, max_forward_return REAL,
                max_adverse_excursion REAL
            );
            CREATE TABLE regime_observations (
                observation_date TEXT, regime TEXT, regime_score REAL,
                regime_confidence REAL, forward_ihsg_return_5d REAL
            );
            CREATE TABLE seasonality_cache (
                ticker TEXT, year INT, month INT, avg_return_pct REAL, win_rate_pct REAL,
                positive_years INT, total_years INT, fetched_month TEXT
            );
            CREATE TABLE analyst_cache (
                ticker TEXT, buy_count INT, hold_count INT, sell_count INT,
                avg_price_target REAL, current_price REAL, fetched_date TEXT
            );
            CREATE TABLE broker_distribution_cache (
                ticker TEXT, trading_date TEXT, top_buyers_json TEXT, top_sellers_json TEXT, fetched_date TEXT
            );
            CREATE TABLE company_financials (
                ticker TEXT, statement_kind TEXT, period_end TEXT, period_type TEXT,
                total_revenue REAL, net_income REAL, operating_income REAL, total_assets REAL,
                total_liabilities REAL, stockholders_equity REAL, cash_and_equivalents REAL,
                total_debt REAL, operating_cash_flow REAL, free_cash_flow REAL, fetched_at TEXT
            );
            CREATE TABLE bandar_detector (
                ticker TEXT, session_date TEXT, broker_accdist TEXT, today_accdist TEXT,
                five_day_accdist TEXT, top1_accdist TEXT, top1_percent REAL, today_percent REAL,
                total_buyer INT, total_seller INT, top3_accdist TEXT, top5_accdist TEXT,
                top10_accdist TEXT, number_broker_buysell INT, vwap REAL, total_value REAL, total_volume INT
            );
            CREATE TABLE forward_estimates_cache (
                ticker TEXT, fetched_date TEXT, forward_eps_1y REAL, revenue_forward_1y REAL, current_price REAL, forward_pe REAL
            );
            CREATE TABLE ticker_notation_cache (
                ticker TEXT, status TEXT, tradeable INT, listing_board TEXT, sector TEXT, sub_sector TEXT,
                haircut_percentage TEXT, notations_json TEXT, market_status TEXT, suspend_info TEXT,
                corp_action_active INT, has_uma INT, fetched_date TEXT
            );
            """
        )
        as_of_fix = (start + timedelta(days=min_bars - 8)).isoformat()
        iev_date = as_of_fix
        for si, t in enumerate(_STOCKS):
            conn.execute(
                "INSERT INTO company_financials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t, "annual", "2023-12-31", "FY", 1e12 * (si + 1), 1e11 * (si + 1), 1.2e11 * (si + 1), 2e12 * (si + 1), 1e12 * (si + 1), 1e12 * (si + 1), 2e11 * (si + 1), 5e11 * (si + 1), 1.5e11 * (si + 1), 1e11 * (si + 1), "2024-06-01"),
            )
            conn.execute(
                "INSERT INTO bandar_detector VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t, iev_date, "BIG ACC", "ACC", "BIG ACC", "ACC", 30.0 + si, 20.0, 50, 40, "BIG ACC", "ACC", "ACC", 90, 100.0, 1e9, 1e6),
            )
            conn.execute(
                "INSERT INTO forward_estimates_cache VALUES (?,?,?,?,?,?)",
                (t, "2024-06-01", 15.0 + si, 1e12, 100.0 + si * 5, 8.0 + si * 0.5),
            )
            conn.execute(
                "INSERT INTO ticker_notation_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t, "STATUS_ACTIVE", 1, "Papan Utama", "Finance", "Banking", "30%", "[]", "close", "", 0, 0 if si > 0 else 1, "2024-06-01"),
            )
        for si, t in enumerate(_STOCKS):
            conn.execute(
                "INSERT INTO seasonality_cache VALUES (?,?,?,?,?,?,?,?)",
                (t, 2024, (si % 12) + 1, 2.5 + si, 60.0 + si, 6, 10, "2024-06"),
            )
            conn.execute(
                "INSERT INTO analyst_cache VALUES (?,?,?,?,?,?,?)",
                (t, 10 + si, 5, 1, 150.0 + si * 10, 100.0 + si * 5, "2024-06-01"),
            )
            conn.execute(
                "INSERT INTO broker_distribution_cache VALUES (?,?,?,?,?)",
                (t, iev_date, '[{"vol":1000}]', '[{"vol":500}]', "2024-06-01"),
            )
        for si, t in enumerate(_STOCKS):
            conn.execute(
                "INSERT INTO earnings_cache VALUES (?,?,?,?,?,?,?,?)",
                (t, 2024, 1, 100.0 + si, 90.0 + si, float(si - 5), float(si - 3), "2024-06-01"),
            )
            conn.execute(
                "INSERT INTO corp_action_cache VALUES (?,?,?,?,?,?,?)",
                (
                    t,
                    "DIVIDEND" if si % 2 == 0 else "RIGHTS",
                    (start + timedelta(days=45 + si)).isoformat(),
                    None,
                    None,
                    "fixture",
                    "2024-06-01",
                ),
            )
            # multi-date IEV for pre-open ADR-002 challenge (same-session open→close)
            for di in range(0, min_bars - 5, max(1, (min_bars - 5) // 20)):
                d_iev = (start + timedelta(days=di)).isoformat()
                conn.execute(
                    "INSERT INTO iev_snapshots VALUES (?,?,?,?,?,?,?)",
                    (
                        d_iev,
                        t,
                        100.0 + si * 0.5 + di * 0.01,
                        si + 1,
                        99.0 + si + (di % 3) * 0.1,
                        f"{d_iev}T08:50:00",
                        0,
                    ),
                )
            # keep last as-of row dense
            conn.execute(
                "INSERT INTO iev_snapshots VALUES (?,?,?,?,?,?,?)",
                (iev_date, t, 100.0 + si * 0.5, si + 1, 99.0 + si, "2024-06-01", 0),
            )
            # labels across dates for walk-forward
            for j in range(20):
                sd = (start + timedelta(days=30 + j)).isoformat()
                conn.execute(
                    "INSERT INTO signal_forward_labels "
                    "(ticker, signal_date, horizon, close_return, "
                    "max_forward_return, max_adverse_excursion) "
                    "VALUES (?,?,?,?,?,?)",
                    (t, sd, 5, 0.01 * ((si + j) % 7 - 3), 0.02, -0.01),
                )
        for k in range(30):
            conn.execute(
                "INSERT INTO regime_observations VALUES (?,?,?,?,?)",
                (
                    (start + timedelta(days=20 + k)).isoformat(),
                    "risk_on" if k % 3 else "risk_off",
                    0.5 + (k % 5) * 0.1,
                    0.7,
                    0.01 * ((k % 5) - 2),
                ),
            )

        # Challenge axis: broker graph + observations + market context
        import json

        conn.executescript(
            """
            CREATE TABLE broker_daily_flow (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                broker_code TEXT NOT NULL,
                net_value REAL,
                buy_value REAL,
                sell_value REAL
            );
            CREATE TABLE learning_observations (
                id INTEGER PRIMARY KEY,
                purpose TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                decision_payload_json TEXT NOT NULL
            );
            CREATE TABLE market_context_snapshots (
                as_of_date TEXT NOT NULL,
                regime TEXT NOT NULL,
                factors_json TEXT NOT NULL
            );
            """
        )
        factor_names = ["vix", "eido", "usd_idr", "idx_trend", "idx_breadth", "foreign_flow"]
        mctx_rows = []
        for k in range(min_bars - 10):
            d = (start + timedelta(days=k)).isoformat()
            regime = "STRESSED" if k % 7 == 0 else ("BULL" if k % 3 == 0 else "NEUTRAL")
            factors = [
                {"name": n, "value": float((k + i * 3) % 50) / 10.0}
                for i, n in enumerate(factor_names)
            ]
            mctx_rows.append((d, regime, json.dumps(factors)))
        conn.executemany(
            "INSERT INTO market_context_snapshots VALUES (?,?,?)",
            mctx_rows,
        )
        brokers = ("YP", "KK", "XL", "RX", "AK", "CC", "PD", "MG")
        flow_rows = []
        for i in range(min_bars):
            d = (start + timedelta(days=i)).isoformat()
            for si, t in enumerate(_STOCKS[:10]):
                for bi, b in enumerate(brokers):
                    # multi-broker net-buy co-occurrence on same day/ticker
                    net = 1e8 * (1 + (si + bi + i) % 5) if bi < 4 + (i % 3) else -5e7
                    flow_rows.append((t, d, b, net, max(net, 0), max(-net, 0)))
        conn.executemany(
            "INSERT INTO broker_daily_flow VALUES (?,?,?,?,?,?)",
            flow_rows,
        )

        obs_rows = []
        groups = [
            "institutional_flow",
            "setup_quality",
            "sector_context",
            "company_quality_context",
        ]
        flow_keys = ["cons", "streak", "vwap", "flow", "inst"]
        for i in range(min(40, min_bars - 5)):
            d = (start + timedelta(days=20 + i)).isoformat()
            captured = f"{d}T09:00:00"
            for si, t in enumerate(_STOCKS):
                seed = (si + 1) * 17 + i * 3
                excess = ((seed % 11) - 5) / 100.0
                raw = 40.0 + (seed % 50)
                flow_signals = [
                    {"key": k, "score": float((seed + j * 7) % 100), "weight": 0.2}
                    for j, k in enumerate(flow_keys)
                ]
                group_contribs = [
                    {
                        "group": g,
                        "score": float((seed + gi * 11) % 100),
                        "configured_weight": 0.25,
                    }
                    for gi, g in enumerate(groups)
                ]
                fingerprint = {
                    "rsi_at_signal": 40.0 + (seed % 30),
                    "vwap_position_at_signal": ((seed % 20) - 10) / 100.0,
                    "ia_foreign_participation": (seed % 40) / 100.0,
                    "ia_domestic_buy_vwap_distance": ((seed % 15) - 7) / 100.0,
                    "bb_width_pctile_at_signal": (seed % 100) / 100.0,
                    "foreign_concentration_at_signal": (seed % 60) / 100.0,
                    "atr_pct_at_signal": 0.01 + (seed % 10) / 1000.0,
                    "raw_signal_score": raw,
                    "volatility_size_multiplier_at_signal": 0.5 + (seed % 10) / 20.0,
                    "cq_valuation_score": float(seed % 80),
                    "tp_liquidity_score": float((seed * 2) % 80),
                    "tp_volatility_score": float((seed * 3) % 80),
                    # P0 Accum sleeves: BCI + sector breadth extract paths
                    "bci_score": (seed % 50) / 100.0,
                    "sector_breadth": (seed % 80) / 100.0,
                    "peer_breadth": (seed % 80) / 100.0,
                    "benchmark_excess_return_5_session": {
                        "excess_return_pct": excess,
                    },
                }
                gates = []
                if seed % 7 == 0:
                    gates.append("BandarGate")
                if seed % 11 == 0:
                    gates.append("LiquidityGate")
                action = "BLOCKED" if gates else "ALLOW"
                for purpose in (
                    "ACCUMULATION_DISCOVERY",
                    "PRE_OPEN_AUCTION_DIRECTION",
                ):
                    payload = {
                        "ticker": t,
                        "snapshot_date": d,
                        "purpose": purpose,
                        "signal": {
                            "raw_score": raw,
                            "raw_exact_score": raw,
                            "score": raw,
                            "alpha_trigger_score": {
                                "group_contributions": group_contribs,
                            },
                            "flow_evidence": {
                                "flow_signals": flow_signals,
                                "flow_score_ex_bb": raw * 0.8,
                                "uncapped_strength": raw,
                            },
                            "factors": {
                                "book_pressure": ((seed % 21) - 10) / 10.0,
                                "delta_iev_ratio": ((seed % 15) - 7) / 100.0,
                                "iep_gap_pct": ((seed % 9) - 4) / 100.0,
                                "iev_intensity": float(seed % 50),
                                "spread_pct": 0.001 + (seed % 5) / 1000.0,
                                "bid_offer_imbalance": ((seed % 17) - 8) / 10.0,
                                "delta_iev": float((seed % 30) - 15),
                                "iev": 100.0 + si + i * 0.1,
                                "atr": 1.0 + (seed % 10) / 10.0,
                            },
                        },
                        "candidate": {
                            "iep_gap_pct": ((seed % 9) - 4) / 100.0,
                            "bid_offer_imbalance": ((seed % 17) - 8) / 10.0,
                            "book_pressure": ((seed % 21) - 10) / 10.0,
                            "delta_iev": float((seed % 30) - 15),
                            "delta_iev_ratio": ((seed % 15) - 7) / 100.0,
                            "iev_intensity": float(seed % 50),
                            "iev": 100.0 + si + i * 0.1,
                            "spread_pct": 0.001 + (seed % 5) / 1000.0,
                            "atr": 1.0 + (seed % 10) / 10.0,
                            "opening_broker_backing_score": float(10 + (seed % 40)),
                            "fvwap_discount_pct": ((seed % 25) - 12) / 10.0,
                        },
                        "trade_setup": {
                            "action": action,
                            "blocking_gates": gates,
                            "signal_multiplier": 0.8 + (seed % 5) / 10.0,
                        },
                        "sub_signal_fingerprint": fingerprint,
                    }
                    obs_rows.append((purpose, captured, json.dumps(payload)))
        conn.executemany(
            "INSERT INTO learning_observations (purpose, captured_at, decision_payload_json) "
            "VALUES (?,?,?)",
            obs_rows,
        )
        conn.commit()
    finally:
        conn.close()
    return path
