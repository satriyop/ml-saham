"""Ch.31 Earnings quality — Sloan accrual anomaly & Huber robust regression."""

from __future__ import annotations

from collections import defaultdict
import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_company_financials
from ml_saham.eval.metrics import rank_ic

META = get_meta("earnings-quality")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menilai kualitas laba menggunakan Sloan Accrual Ratio = (Net Income - Operating Cash Flow) / Total Assets.",
        "  Di IDX, emiten dengan laba berbasis arus kas riil (low accruals) secara konsisten outperform emiten ber-akrual kertas tinggi.",
        "",
        "Opsi pendekatan",
        "  1) Sloan Accrual Ratio = (Net Income - OCF) / Total Assets",
        "  2) Huber Robust Regression (tahan outlier laporan keuangan)",
        "  3) Rank IC Sloan Accruals vs Forward Return 20 Hari",
        "",
        "Caveat",
        "  • Laporan keuangan dipublikasikan kuartalan (butuh PIT lag handling)",
        "  • Sektor keuangan (Bank) membutuhkan definisi arus kas khusus",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_company_financials di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.linear_model import HuberRegressor
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        financials = load_company_financials(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not financials:
        raise ChapterDataError(
            "company_financials kosong.",
            hint="ml-saham doctor",
        )

    by_t = defaultdict(list)
    for f in financials:
        by_t[f["ticker"]].append(f)

    accrual_scores: dict[str, float] = {}
    details: dict[str, dict] = {}

    for t, rows in by_t.items():
        if not rows or t not in fwd:
            continue
        cur = rows[0]
        assets = float(cur.get("total_assets") or 1.0)
        net_inc = float(cur.get("net_income") or 0.0)
        ocf = float(cur.get("operating_cash_flow") or 0.0)

        # Sloan Accrual Ratio: (Net Income - OCF) / Assets
        accrual_ratio = (net_inc - ocf) / (assets or 1.0)
        
        # Lower accruals = higher earnings quality = higher score
        quality_score = -accrual_ratio
        accrual_scores[t] = quality_score
        details[t] = {
            "accrual_ratio": accrual_ratio,
            "quality_score": quality_score,
            "net_income": net_inc,
            "ocf": ocf,
        }

    tickers = sorted(accrual_scores.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(tickers)}).")

    scores = [accrual_scores[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    # Huber Robust Regression
    X = np.array([[details[t]["accrual_ratio"]] for t in tickers])
    y = np.array(rets)
    huber = HuberRegressor(max_iter=200)
    huber.fit(X, y)
    coef = float(huber.coef_[0])

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "accrual_ratio": details[tickers[i]]["accrual_ratio"], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=company_financials",
        f"Sloan Accrual Quality Rank IC vs 5d fwd return: {ic:+.3f}",
        f"Huber Robust Regression Sloan Slope Coef:        {coef:+.4f}",
        "",
        "Top High Earnings Quality Names (Low Accruals, Cash-Backed):",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} AccrualRatio={t['accrual_ratio']:+6.2%}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_sloan_accruals": ic,
        "huber_sloan_coef": coef,
    }
    return DemoResult(
        title="Earnings quality · Sloan accruals & Huber regression",
        lines=lines,
        metrics=metrics,
        model="huber_sloan_accrual",
        summary_md=f"# Earnings quality\n\nRank IC={ic:+.3f}. Huber Slope={coef:+.4f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="company_financials di ai-saham",
        bring_back="Sloan Accruals formula + Huber robust regression habit",
    )
