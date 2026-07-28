"""Ch.16 Earnings surprise — SOTA architecture."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
    load_fundie_map,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_earnings
from ml_saham.eval.metrics import rank_ic, metrics_bundle

META = get_meta("earnings-surprise")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  EPS surprise vs ekspektasi — apakah rank-nya prediktif return berikutnya?",
        "",
        "Opsi pendekatan",
        "  1) LightGBM (default) untuk memprediksi post-earnings drift (SOTA)",
        "  2) Naive PE screen (compare) sebagai baseline filter murah",
        "",
        "Caveat",
        "  • fetched_date ≠ announcement PIT — cek lookahead",
        "  • Cache pribadi kadang tanpa estimate → proxy YoY, bukan true surprise",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline naive_pe --against lightgbm",
    ]
    if verbose:
        lines.append("\nPIT: selalu catat fetched_date vs signal_date.")
    return "\n".join(lines)


def _surprise_score(e: dict) -> tuple[float, str] | None:
    try:
        if e.get("eps_surprise_pct") is not None:
            return float(e["eps_surprise_pct"]), "eps_surprise_pct"
        act, est = e.get("eps_actual"), e.get("eps_estimate")
        if act is not None and est is not None and float(est) != 0:
            return (
                100.0 * (float(act) - float(est)) / abs(float(est)),
                "computed_vs_estimate",
            )
        if e.get("eps_yoy_change") is not None:
            return float(e["eps_yoy_change"]), "eps_yoy_change_proxy"
    except (TypeError, ValueError):
        return None
    return None

def _panel(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        earnings = load_earnings(conn, uni)
        if not earnings:
            raise ChapterDataError("earnings_cache kosong.", hint="ml-saham doctor")
        
        fundies = load_fundie_map(conn, uni)
        
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
            
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    by_t: dict[str, dict] = {}
    score_kind = "eps_surprise_pct"
    for e in earnings:
        t = e.get("ticker")
        if not t:
            continue
        scored = _surprise_score(e)
        if scored is None:
            continue
        surp_f, kind = scored
        key = (int(e.get("year") or 0), int(e.get("quarter") or 0))
        prev = by_t.get(t)
        if prev is None or key > prev["_key"]:
            by_t[t] = {**e, "surprise": surp_f, "_key": key}
            score_kind = kind
            
    rows = []
    for t, e in by_t.items():
        if t in fwd:
            try:
                # We want PE ratio. Naive PE usually favors low PE. So score = -PE or 1/PE. 
                # Let's just say a lower PE is better, so score = -PE
                # If no PE, we set to 0 or mean
                pe = float(fundies.get(t, {}).get("pe_ratio_ttm") or 0.0)
                pe_score = -pe if pe > 0 else 0.0 
            except (ValueError, TypeError):
                pe_score = 0.0
                
            yoy = float(e.get("eps_yoy_change") or 0.0)
                
            rows.append({
                "ticker": t,
                "surprise": e["surprise"],
                "yoy": yoy,
                "pe_score": pe_score,
                "fetched_date": e.get("fetched_date"),
                "fwd": float(fwd[t]),
            })

    if len(rows) < 8:
        raise ChapterDataError(f"Panel earnings terlalu kecil (n={len(rows)}).")

    return as_of, rows, bench, score_kind

def _learned_scores(rows: list[dict], model_type: str = "lightgbm") -> tuple[list[float], str, dict[str, float]]:
    import numpy as np
    
    if model_type == "naive_pe":
        # Baseline: Naive PE screen
        scores = [r["pe_score"] for r in rows]
        return scores, "naive_pe", {}
        
    try:
        import lightgbm as lgb
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install lightgbm") from exc
        
    X = np.array([
        [
            r["surprise"] if not np.isnan(r["surprise"]) else 0.0,
            r["yoy"] if not np.isnan(r["yoy"]) else 0.0,
        ]
        for r in rows
    ])
    y = np.array([r["fwd"] for r in rows])
    
    model = lgb.LGBMRegressor(n_estimators=30, max_depth=3, random_state=42, verbose=-1)
    model.fit(X, y)
    scores = model.predict(X).tolist()
    
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        mean_shap = np.abs(shap_values).mean(axis=0)
        importances = {
            "surprise (SHAP)": float(mean_shap[0]),
            "yoy (SHAP)": float(mean_shap[1]),
        }
    except ImportError:
        importances = {
            "surprise (Gain)": float(model.feature_importances_[0]),
            "yoy (Gain)": float(model.feature_importances_[1]),
        }
    return scores, "lightgbm", importances

def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench, score_kind = _panel(ctx)
    learned, model, importances = _learned_scores(rows, model_type="lightgbm")
    
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    ic = rank_ic(learned, rets)

    bundle = metrics_bundle(
        learned,
        rets,
        benchmark_return=bench,
        date_range=(as_of, as_of),
        n_tickers=len(rows),
    )
    
    order = sorted(range(len(rows)), key=lambda i: learned[i], reverse=True)

    imp_str = "  ".join(f"{k}:{v:.3f}" for k, v in importances.items())

    lines = [
        f"as_of={as_of}  n={len(rows)}  horizon=5d  score={score_kind}",
        f"{model} rank IC: {ic:+.3f}",
        f"{model} feat imp: {imp_str}",
        "PIT note: fetched_date di earnings_cache bisa AFTER announcement —",
        "jangan anggap otomatis point-in-time.",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
    lines.append("")
    lines.append(f"Top {model} names:")
    for i in order[:8]:
        r = rows[i]
        lines.append(
            f"  {r['ticker']:<6} score={learned[i]:+.3f} surprise={r['surprise']:+.1f}%  "
            f"fwd={rets[i]:+.2%}  fetched={r.get('fetched_date') or '?'}"
        )

    top = [
        {"ticker": rows[i]["ticker"], "score": learned[i], "surprise": rows[i]["surprise"], "fwd": rets[i]}
        for i in order[:10]
    ]
    return DemoResult(
        title="Earnings surprise · LightGBM (SOTA)",
        lines=lines,
        metrics={
            **bundle,
            "as_of": as_of,
            "n": len(rows),
            "rank_ic_model": ic,
            "benchmark_return": bench,
            "score_kind": score_kind,
            "model": model,
        },
        model=model,
        summary_md=f"# Earnings surprise\n\nIC={ic:.3f}. score={score_kind}.\n",
        scoreboard=True,
        top_names=top,
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench, score_kind = _panel(ctx)
    
    base_model_type = "naive_pe"
    if "lgbm" in baseline.lower() or "lightgbm" in baseline.lower():
        base_model_type = "lightgbm"
        
    ag_model_type = "lightgbm"
    if "naive" in against.lower() or "pe" in against.lower():
        ag_model_type = "naive_pe"
        
    base_scores, base_name, _ = _learned_scores(rows, model_type=base_model_type)
    ag_scores, ag_name, _ = _learned_scores(rows, model_type=ag_model_type)

    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    
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
        f"{baseline}: rank_ic={ic_b:+.3f}  ({base_name})",
        f"{against}:  rank_ic={ic_a:+.3f}  ({ag_name})",
        f"overlap top10: {len(set(top_b) & set(top_a))}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd: {bench:+.2%}")
        
    compare = {
        "baseline": {"id": baseline, "rank_ic": ic_b, "top10": top_b, "model": base_name},
        "against": {"id": against, "rank_ic": ic_a, "top10": top_a, "model": ag_name},
        "as_of": as_of,
        "benchmark_return": bench,
        "n": len(rows),
    }
    return CompareResult(
        title=f"Compare · {baseline} vs {against}",
        lines=lines,
        metrics={"rank_ic_baseline": ic_b, "rank_ic_against": ic_a, "n": len(rows)},
        compare=compare,
        model=f"{baseline}_vs_{against}",
        summary_md=(
            f"# Compare earnings-surprise\n\n`{baseline}` vs `{against}` as_of={as_of}.\n"
        ),
        scoreboard=True,
    )

def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="earnings_cache / surprise pipeline ai-saham",
        bring_back="surprise (atau YoY proxy) rank IC + fetched_date PIT habit",
    )
