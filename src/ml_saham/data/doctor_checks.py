"""Doctor checks for MVP / v1.1 / later data tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ml_saham.data.aisaham_read import (
    broker_summaries_date_range,
    candle_date_range,
    connect,
    count_rows,
    distinct_sector_count,
    distinct_ticker_count,
    has_ihsg,
    insider_date_stats,
    table_columns,
    table_exists,
    ticker_candle_count,
)
from ml_saham.data.universe import default_universe

Status = str  # ok | partial | missing

_MIN_SECTORS_V11 = 3


@dataclass
class CheckItem:
    name: str
    status: Status
    detail: str = ""
    hard: bool = True  # hard missing fails its tier


@dataclass
class TierReport:
    name: str
    status: Status
    items: list[CheckItem] = field(default_factory=list)

    def recompute(self) -> None:
        if not self.items:
            self.status = "missing"
            return
        statuses = {i.status for i in self.items}
        if statuses == {"ok"}:
            self.status = "ok"
        elif "ok" in statuses or "partial" in statuses:
            self.status = "partial"
        else:
            self.status = "missing"


@dataclass
class DoctorReport:
    db_path: Path
    db_exists: bool
    mvp: TierReport
    v1_1: TierReport = field(
        default_factory=lambda: TierReport(name="v1.1 data", status="missing")
    )
    phase2: TierReport = field(
        default_factory=lambda: TierReport(name="Phase-2 data", status="missing")
    )
    integrity: TierReport = field(
        default_factory=lambda: TierReport(name="Data integrity", status="missing")
    )
    universe_tickers: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)
    deep: bool = False

    @property
    def mvp_hard_ok(self) -> bool:
        if not self.db_exists:
            return False
        hard = [i for i in self.mvp.items if i.hard]
        if not hard:
            return False
        return all(i.status == "ok" for i in hard)

    @property
    def v1_1_hard_ok(self) -> bool:
        if not self.mvp_hard_ok:
            return False
        hard = [i for i in self.v1_1.items if i.hard]
        if not hard:
            return False
        return all(i.status == "ok" for i in hard)

    @property
    def phase2_hard_ok(self) -> bool:
        if not self.mvp_hard_ok:
            return False
        hard = [i for i in self.phase2.items if i.hard]
        if not hard:
            return False
        return all(i.status == "ok" for i in hard)

    def tier_ok(self, required_data: str) -> bool:
        if required_data == "mvp":
            return self.mvp_hard_ok
        if required_data == "v1_1":
            return self.v1_1_hard_ok
        if required_data == "phase2":
            return self.phase2_hard_ok
        return self.mvp_hard_ok


_MVP_REQUIRED_COLS: dict[str, set[str]] = {
    "candles": {"ticker", "date", "open", "high", "low", "close", "volume"},
    "company_fundamentals": {
        "ticker",
        "fetched_date",
        "pe_ratio_ttm",
        "roe_ttm",
        "pbv",
    },
    "broker_summaries": {
        "ticker",
        "date",
        "foreign_buy_value",
        "foreign_sell_value",
        "foreign_buy_lot",
        "foreign_sell_lot",
        "total_value",
    },
    "foreign_flow_points": {"ticker", "date", "net_val", "net_lot", "source"},
    "shareholding_composition": {
        "ticker",
        "fetched_date",
        "institution_pct",
        "individual_pct",
    },
}

_INSIDER_COLS = {
    "ticker",
    "transaction_date",
    "action_type",
    "shares",
    "role",
    "fetched_date",
}


def _check_table(
    conn,
    name: str,
    *,
    required_cols: set[str] | None = None,
    hard: bool = True,
    extra_detail: str = "",
) -> CheckItem:
    if not table_exists(conn, name):
        return CheckItem(name, "missing", "tabel tidak ada", hard=hard)
    cols = table_columns(conn, name)
    missing_cols = sorted((required_cols or set()) - cols)
    n = count_rows(conn, name)
    tickers = distinct_ticker_count(conn, name)
    if missing_cols:
        return CheckItem(
            name,
            "partial" if n > 0 else "missing",
            f"kolom hilang: {', '.join(missing_cols)}; rows={n}",
            hard=hard,
        )
    if n == 0:
        return CheckItem(name, "missing", "tabel kosong", hard=hard)
    detail = f"rows={n}"
    if tickers:
        detail += f" tickers={tickers}"
    if extra_detail:
        detail += f" {extra_detail}"
    return CheckItem(name, "ok", detail.strip(), hard=hard)


def _sector_check(conn) -> CheckItem:
    """MVP soft sector presence (stock_meta OR notation)."""
    sector_ok = False
    sector_detail = ""
    for tname, col_hint in (
        ("stock_meta", "sector"),
        ("ticker_notation_cache", "sector"),
    ):
        if table_exists(conn, tname) and count_rows(conn, tname) > 0:
            cols = table_columns(conn, tname)
            if "ticker" in cols and (
                col_hint in cols or "sub_sector" in cols or "industry" in cols
            ):
                sector_ok = True
                sector_detail = (
                    f"{tname} rows={count_rows(conn, tname)} "
                    f"tickers={distinct_ticker_count(conn, tname)}"
                )
                break
    return CheckItem(
        "sector_meta",
        "ok" if sector_ok else "partial",
        sector_detail or "stock_meta/ticker_notation_cache belum siap",
        hard=False,
    )


def _v11_sector_coverage(conn) -> CheckItem:
    n = distinct_sector_count(conn)
    if n >= _MIN_SECTORS_V11:
        return CheckItem(
            "sector_coverage",
            "ok",
            f"distinct_sectors={n} (min {_MIN_SECTORS_V11})",
            hard=True,
        )
    if n > 0:
        return CheckItem(
            "sector_coverage",
            "partial",
            f"distinct_sectors={n} < {_MIN_SECTORS_V11}",
            hard=True,
        )
    return CheckItem(
        "sector_coverage",
        "missing",
        "tidak ada sector di stock_meta/notation",
        hard=True,
    )


def _v11_insider(conn) -> CheckItem:
    base = _check_table(
        conn,
        "insider_cache",
        required_cols=_INSIDER_COLS,
        hard=True,
    )
    if base.status == "missing":
        return base
    stats = insider_date_stats(conn)
    detail = (
        f"{base.detail} usable={stats['usable']} "
        f"absurd_dates={stats['absurd']}"
    )
    if stats["usable"] <= 0:
        return CheckItem(
            "insider_cache",
            "partial" if stats["total"] > 0 else "missing",
            detail + " (tidak ada BUY/SELL usable setelah scrub)",
            hard=True,
        )
    status: Status = "ok"
    if stats["absurd"] > 0 and stats["absurd"] >= stats["usable"]:
        status = "partial"
    elif base.status != "ok":
        status = base.status
    return CheckItem("insider_cache", status, detail, hard=True)


def _phase2_checks(conn) -> list[CheckItem]:
    from ml_saham.data.phase2_read import headline_table_name

    items: list[CheckItem] = []
    items.append(
        _check_table(
            conn,
            "earnings_cache",
            required_cols={"ticker", "year", "quarter", "eps_surprise_pct", "fetched_date"},
            hard=True,
        )
    )
    # corp: either cache or events
    if table_exists(conn, "corp_action_cache") and count_rows(conn, "corp_action_cache") > 0:
        items.append(
            _check_table(
                conn,
                "corp_action_cache",
                required_cols={"ticker", "event_type", "ex_date"},
                hard=True,
            )
        )
    elif table_exists(conn, "corporate_action_events") and count_rows(
        conn, "corporate_action_events"
    ) > 0:
        items.append(
            CheckItem(
                "corporate_action_events",
                "ok",
                f"rows={count_rows(conn, 'corporate_action_events')}",
                hard=True,
            )
        )
    else:
        items.append(
            CheckItem(
                "corp_actions",
                "missing",
                "corp_action_cache / corporate_action_events kosong",
                hard=True,
            )
        )

    items.append(
        _check_table(
            conn,
            "iev_snapshots",
            required_cols={"date", "ticker", "iev", "rank"},
            hard=True,
        )
    )
    # Live learning plane (ai-saham SSOT). Soft here; integrity block deep-dives purpose counts.
    items.append(
        _check_table(
            conn,
            "learning_observations",
            required_cols={"purpose", "decision_payload_json"},
            hard=False,
        )
    )
    items.append(
        _check_table(
            conn,
            "learning_outcome_labels",
            required_cols={"observation_id", "contract_id"},
            hard=False,
        )
    )
    if table_exists(conn, "learning_evaluations"):
        items.append(
            _check_table(
                conn,
                "learning_evaluations",
                required_cols=set(),
                hard=False,
            )
        )
    else:
        items.append(
            CheckItem(
                "learning_evaluations",
                "missing",
                "optional cohort/evaluate store — not required for challenge panels",
                hard=False,
            )
        )
    # Legacy names (retired) — soft only if present; do not require for phase-2 ok
    if table_exists(conn, "signal_forward_labels"):
        items.append(
            _check_table(
                conn,
                "signal_forward_labels",
                required_cols={"ticker", "signal_date", "horizon", "close_return"},
                hard=False,
            )
        )
    if table_exists(conn, "candidate_observations"):
        items.append(
            CheckItem(
                "candidate_observations",
                "ok",
                "legacy table present — prefer learning_observations",
                hard=False,
            )
        )
    items.append(
        _check_table(
            conn,
            "regime_observations",
            required_cols={"observation_date", "regime"},
            hard=False,
        )
    )
    hname = headline_table_name(conn)
    if hname:
        items.append(
            CheckItem(
                "headlines",
                "ok",
                f"{hname} rows={count_rows(conn, hname)}",
                hard=False,
            )
        )
    else:
        items.append(
            CheckItem(
                "headlines",
                "missing",
                "tidak ada tabel headline — Ch.10 pakai korpus sintetis",
                hard=False,
            )
        )
    return items


def _integrity_checks(conn, *, deep: bool) -> list[CheckItem]:
    """Observation health + cross-table honesty (challenge data plane)."""
    items: list[CheckItem] = []

    # learning_observations by purpose
    if table_exists(conn, "learning_observations"):
        rows = conn.execute(
            "SELECT purpose, COUNT(*) AS n FROM learning_observations GROUP BY purpose"
        ).fetchall()
        by_purpose = {str(r[0]): int(r[1]) for r in rows}
        total = sum(by_purpose.values())
        accum_n = by_purpose.get("ACCUMULATION_DISCOVERY", 0)
        pre_n = by_purpose.get("PRE_OPEN_AUCTION_DIRECTION", 0)
        if total == 0:
            items.append(
                CheckItem(
                    "learning_observations",
                    "missing",
                    "table empty — challenge accum/pre-open will fail",
                    hard=False,
                )
            )
        elif accum_n < 20 and pre_n < 20:
            items.append(
                CheckItem(
                    "learning_observations",
                    "partial",
                    f"rows={total} accum={accum_n} pre_open={pre_n} (thin for challenge)",
                    hard=False,
                )
            )
        else:
            detail = f"rows={total} accum={accum_n} pre_open={pre_n}"
            if deep and by_purpose:
                bits = ", ".join(f"{k}={v}" for k, v in sorted(by_purpose.items())[:8])
                detail += f" [{bits}]"
            items.append(CheckItem("learning_observations", "ok", detail, hard=False))
    else:
        items.append(
            CheckItem(
                "learning_observations",
                "missing",
                "no table — engine challenge needs ai-saham observation capture",
                hard=False,
            )
        )

    items.append(
        _check_table(
            conn,
            "market_context_snapshots",
            required_cols={"as_of_date", "regime"},
            hard=False,
        )
    )

    cmin, cmax = candle_date_range(conn)
    bmin, bmax = broker_summaries_date_range(conn)
    if cmin and cmax and bmin and bmax:
        # Overlap honesty: broker window should intersect candles
        if bmax < cmin or bmin > cmax:
            items.append(
                CheckItem(
                    "date_overlap",
                    "partial",
                    f"candles {cmin}..{cmax} vs broker {bmin}..{bmax} (no overlap)",
                    hard=False,
                )
            )
        else:
            items.append(
                CheckItem(
                    "date_overlap",
                    "ok",
                    f"candles {cmin}..{cmax}; broker {bmin}..{bmax}",
                    hard=False,
                )
            )
    else:
        items.append(
            CheckItem(
                "date_overlap",
                "partial",
                "cannot assess candle/broker date overlap",
                hard=False,
            )
        )

    if deep and table_exists(conn, "company_fundamentals"):
        cols = table_columns(conn, "company_fundamentals")
        if "fetched_date" in cols:
            row = conn.execute(
                "SELECT MIN(fetched_date), MAX(fetched_date), COUNT(DISTINCT fetched_date) "
                "FROM company_fundamentals"
            ).fetchone()
            fmin, fmax, n_snap = (row[0], row[1], int(row[2] or 0)) if row else (None, None, 0)
            status: Status = "ok" if n_snap >= 1 else "missing"
            if n_snap == 1:
                status = "partial"
            items.append(
                CheckItem(
                    "fundamentals_pit",
                    status,
                    f"fetched_date {fmin}..{fmax} distinct_snapshots={n_snap}",
                    hard=False,
                )
            )

    if deep and has_ihsg(conn):
        n = ticker_candle_count(conn, "IHSG")
        items.append(
            CheckItem(
                "ihsg_depth",
                "ok" if n >= 60 else "partial",
                f"IHSG bars={n} (need ~60+ for regime/walk-forward comfort)",
                hard=False,
            )
        )

    return items


def run_doctor(db_path: Path | str, *, deep: bool = False) -> DoctorReport:
    path = Path(db_path)
    empty_v11 = TierReport(name="v1.1 data", status="missing", items=[])
    empty_p2 = TierReport(name="Phase-2 data", status="missing", items=[])
    empty_int = TierReport(name="Data integrity", status="missing", items=[])
    if not path.is_file():
        mvp = TierReport(name="MVP data", status="missing", items=[])
        return DoctorReport(
            db_path=path,
            db_exists=False,
            mvp=mvp,
            v1_1=empty_v11,
            phase2=empty_p2,
            integrity=empty_int,
            deep=deep,
            remediation=[
                "Set --db PATH or env ML_SAHAM_DB.",
                "In ai-saham: saham fetch market --universe lq45",
            ],
        )

    with connect(path) as conn:
        cmin, cmax = candle_date_range(conn)
        candle_extra = ""
        if cmin and cmax:
            candle_extra = f"range={cmin}..{cmax}"
        items: list[CheckItem] = [
            _check_table(
                conn,
                "candles",
                required_cols=_MVP_REQUIRED_COLS["candles"],
                hard=True,
                extra_detail=candle_extra,
            ),
        ]
        if has_ihsg(conn):
            items.append(
                CheckItem(
                    "IHSG",
                    "ok",
                    f"bars={ticker_candle_count(conn, 'IHSG')}",
                    hard=True,
                )
            )
        else:
            items.append(
                CheckItem("IHSG", "missing", "tidak ada ticker IHSG di candles", hard=True)
            )

        items.append(
            _check_table(
                conn,
                "company_fundamentals",
                required_cols=_MVP_REQUIRED_COLS["company_fundamentals"],
                hard=True,
            )
        )
        items.append(_sector_check(conn))

        bmin, bmax = broker_summaries_date_range(conn)
        broker_extra = f"range={bmin}..{bmax}" if bmin and bmax else ""
        items.append(
            _check_table(
                conn,
                "broker_summaries",
                required_cols=_MVP_REQUIRED_COLS["broker_summaries"],
                hard=True,
                extra_detail=broker_extra,
            )
        )
        items.append(
            _check_table(
                conn,
                "foreign_flow_points",
                required_cols=_MVP_REQUIRED_COLS["foreign_flow_points"],
                hard=True,
            )
        )
        items.append(
            _check_table(
                conn,
                "shareholding_composition",
                required_cols=_MVP_REQUIRED_COLS["shareholding_composition"],
                hard=False,
            )
        )
        items.append(
            _check_table(
                conn,
                "broker_daily_flow",
                required_cols={"ticker", "date", "broker_code"},
                hard=False,
            )
        )

        universe = default_universe(conn)
        mvp = TierReport(name="MVP data", status="missing", items=items)
        mvp.recompute()

        v11_items = [_v11_sector_coverage(conn), _v11_insider(conn)]
        v1_1 = TierReport(name="v1.1 data", status="missing", items=v11_items)
        v1_1.recompute()

        p2_items = _phase2_checks(conn)
        phase2 = TierReport(name="Phase-2 data", status="missing", items=p2_items)
        phase2.recompute()

        int_items = _integrity_checks(conn, deep=deep)
        integrity = TierReport(name="Data integrity", status="missing", items=int_items)
        integrity.recompute()

        remediation: list[str] = []
        if not mvp_hard_ok_items(items):
            remediation.append(
                "In ai-saham: saham fetch market --universe lq45 "
                "(candles + broker + enrichment)."
            )
        if not any(i.name == "IHSG" and i.status == "ok" for i in items):
            remediation.append(
                "Ensure IHSG is fetched (market fetch should include benchmark)."
            )
        if not universe:
            remediation.append(
                "Empty universe: cache more LQ45-like tickers in candles."
            )
        if not all(i.status == "ok" for i in v11_items if i.hard):
            remediation.append(
                "For v1.1: fill stock_meta/sector + insider_cache enrichment."
            )
            if any(
                i.name == "insider_cache" and "absurd" in i.detail for i in v11_items
            ):
                remediation.append(
                    "Insider: scrub absurd dates (<1990); re-fetch placeholders."
                )
        if not all(i.status == "ok" for i in p2_items if i.hard):
            remediation.append(
                "For phase-2: earnings_cache, corp actions, iev_snapshots "
                "(+ iev_snapshot_history when available)."
            )
        if any(i.status != "ok" for i in int_items):
            remediation.append(
                "For challenge path: capture learning_observations "
                "(ACCUMULATION_DISCOVERY + PRE_OPEN_AUCTION_DIRECTION), "
                "optional learning_outcome_labels, and keep candles (incl. IHSG) aligned. "
                "Do not require candidate_observations / signal_forward_labels "
                "(retired). See: ml-saham vet | docs/challenge_product.md"
            )

        return DoctorReport(
            db_path=path.resolve(),
            db_exists=True,
            mvp=mvp,
            v1_1=v1_1,
            phase2=phase2,
            integrity=integrity,
            universe_tickers=universe,
            remediation=remediation,
            deep=deep,
        )


def mvp_hard_ok_items(items: list[CheckItem]) -> bool:
    return all(i.status == "ok" for i in items if i.hard)


def _format_tier(lines: list[str], tier: TierReport) -> None:
    lines.append(f"{tier.name}: {tier.status}")
    for item in tier.items:
        detail = f"  {item.name:<22} {item.status}"
        if item.detail:
            detail += f"  {item.detail}"
        if not item.hard and item.status != "ok":
            detail += "  (soft)"
        lines.append(detail)


def format_doctor_report(report: DoctorReport) -> str:
    lines = [f"DB: {report.db_path}"]
    if report.deep:
        lines.append("Mode: deep integrity")
    if not report.db_exists:
        lines.append("MVP data: missing")
        lines.append("  (DB file not found)")
        lines.append("v1.1 data: missing")
        lines.append("Phase-2 data: missing")
        lines.append("Data integrity: missing")
    else:
        _format_tier(lines, report.mvp)
        _format_tier(lines, report.v1_1)
        _format_tier(lines, report.phase2)
        _format_tier(lines, report.integrity)
        lines.append(
            f"Universe default: {len(report.universe_tickers)} tickers"
            + (
                f" ({', '.join(report.universe_tickers[:8])}"
                + ("…" if len(report.universe_tickers) > 8 else "")
                + ")"
                if report.universe_tickers
                else ""
            )
        )
    if report.remediation:
        lines.append("Remediation:")
        for r in report.remediation:
            lines.append(f"  - {r}")
    return "\n".join(lines)


def integrity_score(report: DoctorReport) -> dict[str, float | int | str]:
    """Numeric integrity summary for data-integrity challenge."""
    items = report.integrity.items if report.db_exists else []
    if not items:
        return {"score": 0.0, "n_ok": 0, "n_total": 0, "status": "missing"}
    n_ok = sum(1 for i in items if i.status == "ok")
    n_partial = sum(1 for i in items if i.status == "partial")
    n_total = len(items)
    score = (n_ok + 0.5 * n_partial) / n_total if n_total else 0.0
    return {
        "score": round(score, 4),
        "n_ok": n_ok,
        "n_partial": n_partial,
        "n_total": n_total,
        "status": report.integrity.status,
    }
