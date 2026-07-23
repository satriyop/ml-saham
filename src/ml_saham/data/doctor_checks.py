"""Doctor checks for MVP / later data tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ml_saham.data.aisaham_read import (
    broker_summaries_date_range,
    candle_date_range,
    connect,
    count_rows,
    distinct_ticker_count,
    has_ihsg,
    table_columns,
    table_exists,
    ticker_candle_count,
)
from ml_saham.data.universe import default_universe

Status = str  # ok | partial | missing


@dataclass
class CheckItem:
    name: str
    status: Status
    detail: str = ""
    hard: bool = True  # hard missing fails MVP tier


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
    universe_tickers: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)

    @property
    def mvp_hard_ok(self) -> bool:
        if not self.db_exists:
            return False
        hard = [i for i in self.mvp.items if i.hard]
        if not hard:
            return False
        return all(i.status == "ok" for i in hard)


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


def run_doctor(db_path: Path | str) -> DoctorReport:
    path = Path(db_path)
    if not path.is_file():
        mvp = TierReport(name="MVP data", status="missing", items=[])
        return DoctorReport(
            db_path=path,
            db_exists=False,
            mvp=mvp,
            remediation=[
                "Set --db PATH atau env ML_SAHAM_DB.",
                "Atau di ai-saham: saham fetch market --universe lq45",
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

        # sector: stock_meta OR ticker_notation_cache
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
        items.append(
            CheckItem(
                "sector_meta",
                "ok" if sector_ok else "partial",
                sector_detail or "stock_meta/ticker_notation_cache belum siap",
                hard=False,
            )
        )

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

        remediation: list[str] = []
        if not mvp_hard_ok_items(items):
            remediation.append(
                "Di ai-saham: saham fetch market --universe lq45 "
                "(candles + broker + enrichment)."
            )
        if not any(i.name == "IHSG" and i.status == "ok" for i in items):
            remediation.append(
                "Pastikan IHSG ikut ter-fetch (fetch market selalu include benchmark)."
            )
        if not universe:
            remediation.append(
                "Universe kosong: cache lebih banyak ticker LQ45-like di candles."
            )

        return DoctorReport(
            db_path=path.resolve(),
            db_exists=True,
            mvp=mvp,
            universe_tickers=universe,
            remediation=remediation,
        )


def mvp_hard_ok_items(items: list[CheckItem]) -> bool:
    return all(i.status == "ok" for i in items if i.hard)


def format_doctor_report(report: DoctorReport) -> str:
    lines = [f"DB: {report.db_path}"]
    if not report.db_exists:
        lines.append("MVP data: missing")
        lines.append("  (file DB tidak ada)")
    else:
        lines.append(f"MVP data: {report.mvp.status}")
        for item in report.mvp.items:
            mark = item.status
            detail = f"  {item.name:<22} {mark}"
            if item.detail:
                detail += f"  {item.detail}"
            if not item.hard and item.status != "ok":
                detail += "  (soft)"
            lines.append(detail)
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
