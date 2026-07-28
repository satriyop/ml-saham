"""Ch.25 Financial quality — Piotroski F-Score & accounting quality signals."""

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

META = get_meta("financial-quality")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menilai kualitas фундаментал & akuntansi perusahaan menggunakan matriks 9 sinyal",
        "  Piotroski F-Score (Profitabilitas, Likuiditas/Leverage, Efisiensi Operasional).",
        "",
        "Opsi pendekatan",
        "  1) Matriks 9 Sinyal Akuntansi Piotroski F-Score (Score 0-9)",
        "  2) Logistic Regression / Decision Tree memprediksi Outperformer Return",
        "  3) Rank IC F-Score vs Forward Return 20 Hari",
        "",
        "Caveat",
        "  • Laporan keuangan dipublikasikan kuartalan (PIT delay)",
        "  • Perusahaan sektor keuangan (Bank) membutuhkan penyesuaian F-Score khusus",
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
        from sklearn.linear_model import LogisticRegression
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

    # Calculate Piotroski F-Score signals per ticker
    scores: dict[str, float] = {}
    f_details: dict[str, list[int]] = {}

    by_t = defaultdict(list)
    for f in financials:
        by_t[f["ticker"]].append(f)

    for t, rows in by_t.items():
        if not rows or t not in fwd:
            continue
        cur = rows[0]
        prev = rows[1] if len(rows) > 1 else cur

        assets = float(cur.get("total_assets") or 1.0)
        net_inc = float(cur.get("net_income") or 0.0)
        ocf = float(cur.get("operating_cash_flow") or 0.0)
        roa_cur = net_inc / assets
        roa_prev = float(prev.get("net_income") or 0.0) / (float(prev.get("total_assets") or 1.0))

        debt_cur = float(cur.get("total_debt") or 0.0) / assets
        debt_prev = float(prev.get("total_debt") or 0.0) / (float(prev.get("total_assets") or 1.0))

        rev_cur = float(cur.get("total_revenue") or 0.0)
        rev_prev = float(prev.get("total_revenue") or 0.0)

        # 9 Piotroski Signals
        f1 = 1 if roa_cur > 0 else 0
        f2 = 1 if ocf > 0 else 0
        f3 = 1 if roa_cur > roa_prev else 0
        f4 = 1 if ocf > net_inc else 0  # Quality of earnings / accruals
        f5 = 1 if debt_cur < debt_prev else 0
        f6 = 1 if float(cur.get("cash_and_equivalents") or 0) > float(prev.get("cash_and_equivalents") or 0) else 0
        f7 = 1  # Equity dilution placeholder
        f8 = 1 if (net_inc / (rev_cur or 1.0)) > (float(prev.get("net_income") or 0.0) / (rev_prev or 1.0)) else 0
        f9 = 1 if (rev_cur / assets) > (rev_prev / (float(prev.get("total_assets") or 1.0))) else 0

        signals = [f1, f2, f3, f4, f5, f6, f7, f8, f9]
        total_f = sum(signals)
        scores[t] = float(total_f)
        f_details[t] = signals

    tickers = sorted(scores.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(tickers)}).")

    f_scores = [scores[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(f_scores, rets)

    # Fit Logistic Regression on 9 signals predicting positive return
    X = np.array([f_details[t] for t in tickers])
    y = np.array([1 if r > 0 else 0 for r in rets])

    model_acc = 0.5
    if len(set(y.tolist())) >= 2:
        clf = LogisticRegression(max_iter=200)
        clf.fit(X, y)
        model_acc = float(clf.score(X, y))

    order = sorted(range(len(tickers)), key=lambda i: f_scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "f_score": f_scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        f"Piotroski F-Score Rank IC vs 5d fwd return: {ic:+.3f}",
        f"9-Signal Logistic Model In-Sample Accuracy: {model_acc:.1%}",
        "",
        "Top Piotroski F-Score Companies (Score 0-9):",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} F-Score={t['f_score']:.0f}/9  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_f_score": ic,
        "model_accuracy": model_acc,
    }
    return DemoResult(
        title="Financial quality · Piotroski F-Score",
        lines=lines,
        metrics=metrics,
        model="piotroski_f_score_logistic",
        summary_md=f"# Financial quality\n\nRank IC={ic:+.3f}. Accuracy={model_acc:.1%}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="company_financials di ai-saham",
        bring_back="Piotroski F-Score 9-signal matrix + rank IC habit",
    )
