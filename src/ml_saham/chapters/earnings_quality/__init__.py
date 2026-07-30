"""Ch.34 Earnings quality — Sloan accrual anomaly & Huber robust regression."""

from __future__ import annotations

from collections import defaultdict
import math

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
        "  Menilai kualitas laba menggunakan akrual dan arus kas.",
        "  Di IDX, laba berbasis arus kas riil lebih sustain daripada akrual.",
        "",
        "Opsi algoritma",
        "  1) LightGBM classification pada accruals dan cash flow (Default / default)",
        "  2) Simple accrual ratio rank (Baseline / compare)",
        "",
        "Caveat",
        "  • Laporan keuangan dipublikasikan kuartalan (butuh PIT lag handling)",
        "  • Sektor keuangan (Bank) membutuhkan definisi arus kas khusus",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_company_financials di ai-saham.")
    return "\n".join(lines)

def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install -e .") from exc

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

    details: dict[str, dict] = {}
    
    for t, rows in by_t.items():
        if not rows or t not in fwd:
            continue
        cur = rows[0]
        assets = float(cur.get("total_assets") or 1.0)
        net_inc = float(cur.get("net_income") or 0.0)
        ocf = float(cur.get("operating_cash_flow") or 0.0)

        accruals = net_inc - ocf
        accrual_ratio = accruals / (assets or 1.0)
        ocf_ratio = ocf / (assets or 1.0)
        
        details[t] = {
            "accrual_ratio": accrual_ratio,
            "ocf_ratio": ocf_ratio,
            "net_income": net_inc,
            "ocf": ocf,
        }

    tickers = sorted(details.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(tickers)}).")

    X = np.array([[details[t]["accrual_ratio"], details[t]["ocf_ratio"]] for t in tickers])
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    
    # Classification: up (1) or down (0)
    y = (np.array(rets) > 0).astype(int)

    # Note: Using small number of samples in demo, LightGBM might need specific params
    lgbm = LGBMClassifier(n_estimators=10, max_depth=3, random_state=42, verbose=-1, min_child_samples=2)
    lgbm.fit(X, y)
    
    # Predict probability of being positive
    probs = lgbm.predict_proba(X)[:, 1]
    
    ic = rank_ic(probs.tolist(), rets)

    order = sorted(range(len(tickers)), key=lambda i: probs[i], reverse=True)
    top = [
        {"ticker": tickers[i], "prob": probs[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=company_financials",
        f"LightGBM Classification Rank IC vs 5d fwd return: {ic:+.3f}",
        "",
        "Top default Predictions (High Probability of positive return):",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} Prob={t['prob']:+6.2%}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_lgbm": ic,
    }
    return DemoResult(
        title="Earnings quality · LightGBM (default)",
        lines=lines,
        metrics=metrics,
        model="lightgbm_classification",
        summary_md=f"# Earnings quality\n\nRank IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )

def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install -e .") from exc

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

    details: dict[str, dict] = {}
    
    for t, rows in by_t.items():
        if not rows or t not in fwd:
            continue
        cur = rows[0]
        assets = float(cur.get("total_assets") or 1.0)
        net_inc = float(cur.get("net_income") or 0.0)
        ocf = float(cur.get("operating_cash_flow") or 0.0)

        accruals = net_inc - ocf
        accrual_ratio = accruals / (assets or 1.0)
        ocf_ratio = ocf / (assets or 1.0)
        
        details[t] = {
            "accrual_ratio": accrual_ratio,
            "ocf_ratio": ocf_ratio,
        }

    tickers = sorted(details.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(tickers)}).")

    X = np.array([[details[t]["accrual_ratio"], details[t]["ocf_ratio"]] for t in tickers])
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    y = (np.array(rets) > 0).astype(int)

    # Baseline: negative of simple accrual ratio
    baseline_scores = [-details[t]["accrual_ratio"] for t in tickers]
    baseline_ic = rank_ic(baseline_scores, rets)

    # Default: LightGBM classification
    lgbm = LGBMClassifier(n_estimators=10, max_depth=3, random_state=42, verbose=-1, min_child_samples=2)
    lgbm.fit(X, y)
    against_scores = lgbm.predict_proba(X)[:, 1].tolist()
    against_ic = rank_ic(against_scores, rets)

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        "Perbandingan Model Earnings Quality:",
        f"  default (LightGBM):           IC = {against_ic:+.3f}",
        f"  Baseline (Accrual Ratio):  IC = {baseline_ic:+.3f}",
        "",
        "Kesimpulan:",
    ]
    
    if against_ic > baseline_ic:
        lines.append("  Default model (LightGBM) memberikan ranking yang lebih akurat.")
    else:
        lines.append("  Baseline (Accrual Ratio) menang pada batch ini.")

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_against": against_ic,
        "rank_ic_baseline": baseline_ic,
    }

    return DemoResult(
        title="Earnings quality · Default vs Baseline",
        lines=lines,
        metrics=metrics,
        model="compare_lightgbm_accrual",
        summary_md=f"# Compare\n\nDefault IC: {against_ic:+.3f}, Baseline IC: {baseline_ic:+.3f}\n",
        scoreboard=False,
    )

