"""Ch.29 Financial distress — Altman Z-Score & bankruptcy risk filter."""

from __future__ import annotations

from collections import defaultdict

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
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
        "  Mengukur risiko kebangkrutan & distress keuangan menggunakan fitur rasio keuangan.",
        "  Default model belajar threshold nonlinear dari fitur (XGBoost), sedangkan baseline menggunakan",
        "  cut-off statis Altman Z-Score.",
        "",
        "Opsi pendekatan",
        "  1) XGBoost pada komponen Altman Z-Score (Default)",
        "  2) Altman Z-Score threshold (Z' < 1.1) (Baseline / Compare)",
        "",
        "Caveat",
        "  • Z-Score awal dirancang untuk manufaktur; versi EM (Z') disesuaikan untuk saham berkembang",
        "  • Emiten distress bisa mengalami lonjakan harga spekulatif (dead cat bounce)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline altman-z --against xgboost",
    ]
    if verbose:
        lines.append("\nDetail: load_company_financials di ai-saham.")
    return "\n".join(lines)

def _build_rows(ctx: ChapterContext):
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

    rows = []
    for t, fs in by_t.items():
        if not fs or t not in fwd:
            continue
        cur = fs[0]
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
        rows.append({
            "ticker": t,
            "components": [x1, x2, x3, x4, x5],
            "z_score": z_prime,
            "fwd": float(fwd[t]),
        })
    return as_of, rows, bench

def _xgb_scores(X: list[list[float]], y: list[float]) -> tuple[list[float], str, list[float]]:
    import numpy as np

    arr = np.array(X, dtype=float)
    yy = np.array(y, dtype=float)

    try:
        import xgboost as xgb

        model = xgb.XGBRegressor(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
            n_jobs=1,
        )
        model.fit(arr, yy)
        pred = model.predict(arr)
        importances = model.feature_importances_.tolist()
        return pred.tolist(), "xgboost", importances
    except ImportError:
        from sklearn.linear_model import Ridge

        model = Ridge(alpha=1.0, random_state=42)
        model.fit(arr, yy)
        pred = model.predict(arr)
        coef = np.abs(model.coef_)
        imp = (coef / coef.sum()).tolist() if float(coef.sum()) > 0 else [0.0] * arr.shape[1]
        return pred.tolist(), "ridge-fallback", imp

def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench = _build_rows(ctx)
    if len(rows) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(rows)}).")

    X = [r["components"] for r in rows]
    z_scores = [r["z_score"] for r in rows]
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)

    model_scores, model_name, importances = _xgb_scores(X, rets)
    ic_z = rank_ic(z_scores, rets)
    ic_xgb = rank_ic(model_scores, rets)

    safe_count = sum(1 for z in z_scores if z > 2.9)
    grey_count = sum(1 for z in z_scores if 1.1 <= z <= 2.9)
    distress_count = sum(1 for z in z_scores if z < 1.1)

    order = sorted(range(len(rows)), key=lambda i: model_scores[i], reverse=True)
    top = [
        {
            "ticker": rows[i]["ticker"],
            "score": model_scores[i],
            "z_score": z_scores[i],
            "fwd": rets[i]
        }
        for i in order[:10]
    ]

    feature_names = ["X1", "X2", "X3", "X4", "X5"]
    imp_str = ", ".join(f"{name}:{imp:.4f}" for name, imp in zip(feature_names, importances, strict=False))

    lines = [
        f"as_of={as_of}  n_tickers={len(rows)}",
        f"Altman Z'-Score Rank IC vs 5d fwd return: {ic_z:+.3f}",
        f"XGBoost Rank IC vs 5d fwd return:         {ic_xgb:+.3f}",
        f"Risk Zone Distribution: Safe(Z'>2.9)={safe_count}  Grey(1.1-2.9)={grey_count}  Distress(Z'<1.1)={distress_count}",
        f"XGBoost Feature Importances: {imp_str}",
        "",
        "Top Score (XGBoost default):",
    ]

    for t in top[:8]:
        zone_str = "Safe" if t["z_score"] > 2.9 else ("Grey" if t["z_score"] >= 1.1 else "Distress")
        lines.append(
            f"  {t['ticker']:<6} default_score={t['score']:+.3f}  Z'-Score={t['z_score']:+6.2f}  Zone={zone_str:<8}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(rows),
        "rank_ic_z_score": ic_z,
        "rank_ic_xgb": ic_xgb,
        "safe_count": safe_count,
        "grey_count": grey_count,
        "distress_count": distress_count,
        "xgb_importances": dict(zip(feature_names, importances, strict=False)),
    }
    return DemoResult(
        title="Financial distress · XGBoost vs Altman Z'-Score",
        lines=lines,
        metrics=metrics,
        model="xgboost",
        summary_md=f"# Financial distress\n\nRank IC: XGBoost={ic_xgb:+.3f}, Z-Score={ic_z:+.3f}.\nSafe={safe_count}, Distress={distress_count}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench = _build_rows(ctx)
    if len(rows) < 8:
        raise ChapterDataError(f"Panel financials terlalu kecil (n={len(rows)}).")

    X = [r["components"] for r in rows]
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)

    def get_scores(name: str):
        if "altman" in name.lower() or "z-score" in name.lower():
            return [r["z_score"] for r in rows], "altman-z"
        else:
            scores, model_name, _ = _xgb_scores(X, rets)
            return scores, model_name

    base_scores, base_name = get_scores(baseline)
    ag_scores, ag_name = get_scores(against)

    ic_b = rank_ic(base_scores, rets)
    ic_a = rank_ic(ag_scores, rets)

    top_b = [
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: base_scores[i], reverse=True)[:10]
    ]
    top_a = [
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: ag_scores[i], reverse=True)[:10]
    ]

    lines = [
        f"as_of={as_of}  n={len(rows)}",
        f"{base_name}: rank_ic={ic_b:+.3f}",
        f"{ag_name}: rank_ic={ic_a:+.3f}",
        f"overlap top10: {len(set(top_b) & set(top_a))}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd: {bench:+.2%}")

    compare_data = {
        "baseline": {"id": base_name, "rank_ic": ic_b, "top10": top_b},
        "against": {"id": ag_name, "rank_ic": ic_a, "top10": top_a},
        "as_of": as_of,
        "benchmark_return": bench,
    }

    return CompareResult(
        title=f"Compare · {base_name} vs {ag_name}",
        lines=lines,
        metrics={"rank_ic_baseline": ic_b, "rank_ic_against": ic_a, "n": len(rows)},
        compare=compare_data,
        model=f"{base_name}_vs_{ag_name}",
        summary_md=f"# Compare financial-distress\n\n`{base_name}` vs `{ag_name}`.\n",
        scoreboard=True,
    )

