"""Ch.26 Financial distress — Altman Z-Score & bankruptcy risk filter."""

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

META = get_meta("financial-distress")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur risiko kebangkrutan & distress keuangan menggunakan Emerging Market Altman Z-Score",
        "  untuk menyaring emiten berisiko tinggi (Z' < 1.1) demi menghindari downside tail risk.",
        "",
        "Opsi pendekatan",
        "  1) Emerging Market Altman Z-Score (Z' = 0.717 X1 + 0.847 X2 + 3.107 X3 + 0.420 X4 + 0.998 X5)",
        "  2) Zonasi Risiko: Safe Zone (Z' > 2.9), Grey Zone (1.1 - 2.9), Distress Zone (Z' < 1.1)",
        "  3) Multivariate Isolation Forest Anomaly Detection pada Rasio Keuangan",
        "",
        "Caveat",
        "  • Z-Score awal dirancang untuk manufaktur; versi EM (Z') disesuaikan untuk saham berkembang",
        "  • Emiten distress bisa mengalami lonjakan harga spekulatif (dead cat bounce)",
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
        from sklearn.ensemble import IsolationForest
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

    z_scores: dict[str, float] = {}
    z_components: dict[str, list[float]] = {}

    by_t = defaultdict(list)
    for f in financials:
        by_t[f["ticker"]].append(f)

    for t, rows in by_t.items():
        if not rows or t not in fwd:
            continue
        cur = rows[0]
        assets = float(cur.get("total_assets") or 1.0)
        liab = float(cur.get("total_liabilities") or 1.0)
        equity = float(cur.get("stockholders_equity") or 1.0)
        rev = float(cur.get("total_revenue") or 0.0)
        op_inc = float(cur.get("operating_income") or 0.0)
        net_inc = float(cur.get("net_income") or 0.0)
        cash = float(cur.get("cash_and_equivalents") or 0.0)

        # Emerging Market Altman Z-Score components
        x1 = (cash - liab) / assets  # Working capital proxy / Assets
        x2 = net_inc / assets        # Retained earnings proxy / Assets
        x3 = op_inc / assets         # EBIT / Assets
        x4 = equity / (liab or 1.0)  # Equity / Liabilities
        x5 = rev / assets            # Sales / Assets

        z_prime = 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5
        z_scores[t] = z_prime
        z_components[t] = [x1, x2, x3, x4, x5]

    tickers = sorted(z_scores.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(tickers)}).")

    scores = [z_scores[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    # Multivariate Isolation Forest Anomaly Detection
    X = np.array([z_components[t] for t in tickers])
    iso = IsolationForest(contamination=0.1, random_state=42)
    iso_labels = iso.fit_predict(X)

    safe_count = sum(1 for z in scores if z > 2.9)
    grey_count = sum(1 for z in scores if 1.1 <= z <= 2.9)
    distress_count = sum(1 for z in scores if z < 1.1)

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "z_score": scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        f"Altman Z'-Score Rank IC vs 5d fwd return: {ic:+.3f}",
        f"Risk Zone Distribution: Safe(Z'>2.9)={safe_count}  Grey(1.1-2.9)={grey_count}  Distress(Z'<1.1)={distress_count}",
        "",
        "Top Safe Zone Financial Health Companies (Z'-Score):",
    ]

    for t in top[:8]:
        zone_str = "Safe" if t["z_score"] > 2.9 else ("Grey" if t["z_score"] >= 1.1 else "Distress")
        lines.append(
            f"  {t['ticker']:<6} Z'-Score={t['z_score']:+6.2f}  Zone={zone_str:<8}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_z_score": ic,
        "safe_count": safe_count,
        "grey_count": grey_count,
        "distress_count": distress_count,
    }
    return DemoResult(
        title="Financial distress · Altman Z'-Score",
        lines=lines,
        metrics=metrics,
        model="altman_z_score_isolation_forest",
        summary_md=f"# Financial distress\n\nRank IC={ic:+.3f}. Safe={safe_count}, Distress={distress_count}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="company_financials di ai-saham",
        bring_back="Altman Z'-Score EM formula + Distress filter habit",
    )
