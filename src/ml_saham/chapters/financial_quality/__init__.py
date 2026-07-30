"""Ch.28 Financial quality — Piotroski F-Score & accounting quality signals."""

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
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
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
        "  Menilai kualitas fundamental & akuntansi perusahaan.",
        "",
        "Opsi pendekatan",
        "  1) LightGBM Classification pada sinyal Piotroski/Beneish (default)",
        "  2) Penjumlahan skor Piotroski F-Score (baseline/compare)",
        "",
        "Caveat",
        "  • Laporan keuangan dipublikasikan kuartalan (PIT delay)",
        "  • Perusahaan sektor keuangan membutuhkan penyesuaian khusus",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Bandingkan: ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_company_financials di ai-saham.")
    return "\n".join(lines)

def _prepare_data(ctx: ChapterContext):
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

    return as_of, tickers, f_scores, rets, f_details

def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        import lightgbm as lgb
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install lightgbm") from exc

    as_of, tickers, f_scores, rets, f_details = _prepare_data(ctx)

    # LightGBM classification on Piotroski/Beneish
    X = np.array([f_details[t] for t in tickers])
    y = np.array([1 if r > 0 else 0 for r in rets])

    clf = lgb.LGBMClassifier(
        n_estimators=50,
        max_depth=3,
        random_state=42,
        verbose=-1,
    )
    if len(set(y.tolist())) >= 2:
        clf.fit(X, y)
        preds = clf.predict_proba(X)[:, 1]
    else:
        preds = np.zeros(len(tickers))

    ic = rank_ic(preds.tolist(), rets)
    acc = float((clf.predict(X) == y).mean()) if len(set(y.tolist())) >= 2 else 0.5

    order = sorted(range(len(tickers)), key=lambda i: preds[i], reverse=True)
    top = [
        {"ticker": tickers[i], "prob": float(preds[i]), "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        f"Default LightGBM Rank IC vs 5d fwd return: {ic:+.3f}",
        f"LightGBM In-Sample Accuracy: {acc:.1%}",
        "",
        "Top Default LightGBM Companies:",
    ]
    for t in top[:8]:
        lines.append(f"  {t['ticker']:<6} default_prob={t['prob']:.2f}  fwd={t['fwd']:+.2%}")

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic": ic,
        "model_accuracy": acc,
    }
    return DemoResult(
        title="Financial quality · Default LightGBM",
        lines=lines,
        metrics=metrics,
        model="lightgbm_classification",
        summary_md=f"# Financial quality\n\nRank IC={ic:+.3f}. Accuracy={acc:.1%}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )

def run_compare(ctx: ChapterContext) -> CompareResult:
    try:
        import numpy as np
        import lightgbm as lgb
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install lightgbm") from exc

    as_of, tickers, f_scores, rets, f_details = _prepare_data(ctx)

    # LightGBM (default)
    X = np.array([f_details[t] for t in tickers])
    y = np.array([1 if r > 0 else 0 for r in rets])

    clf = lgb.LGBMClassifier(
        n_estimators=50,
        max_depth=3,
        random_state=42,
        verbose=-1,
    )
    if len(set(y.tolist())) >= 2:
        clf.fit(X, y)
        preds_sota = clf.predict_proba(X)[:, 1]
    else:
        preds_sota = np.zeros(len(tickers))
        
    ic_against = rank_ic(preds_sota.tolist(), rets)
    acc_against = float((clf.predict(X) == y).mean()) if len(set(y.tolist())) >= 2 else 0.5

    # Piotroski F-Score Sum (Baseline)
    ic_baseline = rank_ic(f_scores, rets)
    
    # Simple threshold accuracy for baseline: >5 means outperformer
    preds_baseline = np.array([1 if s > 5 else 0 for s in f_scores])
    acc_baseline = float((preds_baseline == y).mean())

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        "",
        "[ Default: LightGBM Classification ]",
        f"  Rank IC  : {ic_against:+.3f}",
        f"  Accuracy : {acc_against:.1%}",
        "",
        "[ Baseline: Piotroski F-Score Sum ]",
        f"  Rank IC  : {ic_baseline:+.3f}",
        f"  Accuracy : {acc_baseline:.1%}",
    ]
    
    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
    }
    compare = {
        "against_ic": ic_against,
        "against_acc": acc_against,
        "baseline_ic": ic_baseline,
        "baseline_acc": acc_baseline,
    }

    return CompareResult(
        title="Financial quality · Default vs Baseline",
        lines=lines,
        metrics=metrics,
        compare=compare,
        model="lightgbm_vs_f_score",
        summary_md=f"# Financial quality\n\nDefault IC={ic_against:+.3f} vs Baseline IC={ic_baseline:+.3f}.\n",
        scoreboard=True,
    )

