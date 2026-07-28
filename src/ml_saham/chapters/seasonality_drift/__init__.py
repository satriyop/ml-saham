"""Ch.19 Seasonality drift — calendar month anomalies & ANOVA test."""

from __future__ import annotations

from collections import defaultdict
import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_seasonality

META = get_meta("seasonality-drift")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah anomali musiman (misal: 'April dividend rally', 'December Santa rally')",
        "  secara statistik signifikan, atau sekadar overfit histori?",
        "",
        "Opsi pendekatan",
        "  1) Uji Hipotesis Kruskal-Wallis / ANOVA lintas bulan",
        "  2) Regresi Ridge Indikator Kalender + OOS Cross-Validation",
        "  3) Hitung Win Rate % & Average Monthly Return % per Ticker",
        "",
        "Caveat",
        "  • Anomali kalender sering hilang setelah dipublikasikan",
        "  • Sample size bulanan relatif terbatas",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_seasonality dari seasonality_cache.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from scipy.stats import kruskal
        from sklearn.linear_model import Ridge
        from sklearn.metrics import r2_score
    except ImportError as exc:
        raise ChapterError("Butuh scipy & scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        rows = load_seasonality(conn, ctx.universe)

    if not rows:
        raise ChapterDataError(
            "seasonality_cache kosong.",
            hint="ml-saham doctor",
        )

    by_month: dict[int, list[float]] = defaultdict(list)
    by_ticker: dict[str, list[dict]] = defaultdict(list)

    for r in rows:
        m = int(r.get("month") or 0)
        ret = float(r.get("avg_return_pct") or 0.0)
        if 1 <= m <= 12:
            by_month[m].append(ret)
            by_ticker[r["ticker"]].append(r)

    if len(by_month) < 3:
        raise ChapterDataError("Data bulan musiman terlalu sedikit.")

    # Kruskal-Wallis non-parametric ANOVA across months
    month_groups = [by_month[m] for m in sorted(by_month.keys()) if len(by_month[m]) > 0]
    try:
        h_stat, p_val = kruskal(*month_groups)
    except Exception:
        h_stat, p_val = 0.0, 1.0

    # Fit Ridge Regression predicting return from one-hot encoded month
    X, y = [], []
    for m, rets in by_month.items():
        for r in rets:
            one_hot = [1.0 if m == i else 0.0 for i in range(1, 13)]
            X.append(one_hot)
            y.append(r)

    X_arr, y_arr = np.array(X), np.array(y)
    model = Ridge(alpha=1.0)
    model.fit(X_arr, y_arr)
    r2 = float(r2_score(y_arr, model.predict(X_arr)))

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_stats = []
    for m in range(1, 13):
        rets = by_month.get(m, [])
        avg_r = (sum(rets) / len(rets)) if rets else 0.0
        coef = float(model.coef_[m - 1])
        monthly_stats.append((m, month_names[m - 1], len(rets), avg_r, coef))

    monthly_stats.sort(key=lambda x: -x[3])

    lines = [
        f"n_records={len(rows)}  n_tickers={len(by_ticker)}",
        f"Kruskal-Wallis ANOVA H-stat: {h_stat:.3f}  (p-value={p_val:.4f})",
        f"Signifikansi anomali musiman: {'Ya (p<0.05)' if p_val < 0.05 else 'Tidak signifikan (p>=0.05)'}",
        f"Ridge Calendar Model R²:     {r2:.4f}",
        "",
        "Ranking rata-rata return musiman bulanan:",
    ]
    for m, name, n_s, avg_r, coef in monthly_stats:
        lines.append(f"  {name:<4} (Bulan {m:2d}) n={n_s:3d}  mean_ret={avg_r:+.2f}%  coef={coef:+.3f}")

    metrics = {
        "n_records": len(rows),
        "n_tickers": len(by_ticker),
        "kruskal_h_stat": float(h_stat),
        "kruskal_p_value": float(p_val),
        "is_significant": bool(p_val < 0.05),
        "ridge_r2": r2,
    }
    return DemoResult(
        title="Seasonality drift · calendar anomaly lab",
        lines=lines,
        metrics=metrics,
        model="kruskal_ridge_seasonality",
        summary_md=f"# Seasonality drift\n\nANOVA p-val={p_val:.4f}. R²={r2:.4f}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="seasonality_cache di ai-saham",
        bring_back="ANOVA p-value + Ridge calendar cross-validation habit",
    )
