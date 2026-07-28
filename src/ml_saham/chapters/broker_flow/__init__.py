"""Ch.6 Broker & foreign flow — who ranks from flow."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    foreign_net_nday,
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    momentum_nday,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.doctor_checks import run_doctor
from ml_saham.eval.metrics import metrics_bundle, rank_ic

META = get_meta("broker-flow")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Ranking dari aliran *who*: net asing / broker summary — bukan volume burst",
        "  (volume anomaly = Ch.8). Fokus: siapa yang lebih agresif beli/jual.",
        "",
        "Opsi pendekatan",
        "  1) LightGBM + SHAP (SOTA/default) pada fitur flow & momentum",
        "  2) Regresi Logistik / Ridge (baseline/compare)",
        "  3) Lab bandar/konsentrasi (opsional, bukan klaim smart-money)",
        "",
        "Caveat",
        "  • Butuh broker_summaries / foreign_flow_points — doctor hard-fail jika hilang",
        "  • Flow ≠ bukti manipulasi; ini ranking riset saja",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline ridge --against lgbm",
    ]
    if verbose:
        lines.append(
            "\nDeepdive stub: komponen accum / foreign-flow score di ai-saham (manual)."
        )
    return "\n".join(lines)


def _panel(ctx: ChapterContext):
    report = run_doctor(ctx.db_path)
    hard_broker = [
        i
        for i in report.mvp.items
        if i.name in {"broker_summaries", "foreign_flow_points"} and i.hard
    ]
    if any(i.status != "ok" for i in hard_broker):
        detail = ", ".join(f"{i.name}={i.status}" for i in hard_broker)
        raise ChapterDataError(
            f"Data broker/foreign belum siap ({detail})."
        )

    with connect(ctx.db_path) as conn:
        if not table_exists(conn, "broker_summaries") and not table_exists(
            conn, "foreign_flow_points"
        ):
            raise ChapterDataError(
                "Tabel broker_summaries/foreign_flow_points hilang."
            )
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        flow = foreign_net_nday(conn, uni, as_of=as_of, window=5)
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    tickers = sorted(set(flow) & set(fwd) & set(mom))
    if len(tickers) < 10:
        raise ChapterDataError(f"Panel flow terlalu kecil (n={len(tickers)}).")
    
    rows = []
    for t in tickers:
        rows.append(
            {
                "ticker": t,
                "flow": float(flow[t]),
                "mom": float(mom[t]),
                "fwd": float(fwd[t]),
            }
        )
    return as_of, rows, bench


def _learned_scores(rows: list[dict], model_type: str = "lgbm") -> tuple[list[float], str, dict[str, float]]:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression, Ridge
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc
        
    flow_z = zscore([r["flow"] for r in rows])
    mom_z = zscore([r["mom"] for r in rows])
    
    X = np.array([
        [
            flow_z[i] if flow_z[i] is not None else 0.0,
            mom_z[i] if mom_z[i] is not None else 0.0,
        ]
        for i in range(len(rows))
    ])
    y_ret = [r["fwd"] for r in rows]
    
    if model_type == "logistic":
        med = sorted(y_ret)[len(y_ret) // 2]
        y = np.array([1 if r >= med else 0 for r in y_ret])
        if len(set(y.tolist())) < 2:
            return [0.0]*len(rows), "logistic-fallback", {}
        model = LogisticRegression(random_state=42)
        model.fit(X, y)
        scores = model.predict_proba(X)[:, 1].tolist()
        importances = {"flow_z": float(model.coef_[0][0]), "mom_z": float(model.coef_[0][1])}
        return scores, "logistic", importances

    elif model_type == "ridge":
        y = np.array(y_ret)
        model = Ridge(alpha=1.0, random_state=42)
        model.fit(X, y)
        scores = model.predict(X).tolist()
        importances = {"flow_z": float(model.coef_[0]), "mom_z": float(model.coef_[1])}
        return scores, "ridge", importances

    else:
        y = np.array(y_ret)
        try:
            import lightgbm as lgb
            model = lgb.LGBMRegressor(n_estimators=50, max_depth=3, random_state=42, verbose=-1)
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
                    "flow_z (SHAP)": float(mean_shap[0]),
                    "mom_z (SHAP)": float(mean_shap[1]),
                }
            except ImportError:
                importances = {
                    "flow_z (Gain)": float(model.feature_importances_[0]),
                    "mom_z (Gain)": float(model.feature_importances_[1]),
                }
            return scores, "lightgbm", importances
        except ImportError:
            model = Ridge(alpha=1.0, random_state=42)
            model.fit(X, y)
            scores = model.predict(X).tolist()
            importances = {"flow_z": float(model.coef_[0]), "mom_z": float(model.coef_[1])}
            return scores, "ridge-fallback", importances


def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench = _panel(ctx)
    learned, model, importances = _learned_scores(rows, model_type="lgbm")
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    ic_learned = rank_ic(learned, rets)

    bundle = metrics_bundle(
        learned,
        rets,
        benchmark_return=bench,
        date_range=(as_of, as_of),
        n_tickers=len(rows),
    )
    
    order = sorted(range(len(rows)), key=lambda i: learned[i], reverse=True)
    top = [
        {
            "ticker": rows[i]["ticker"],
            "score": learned[i],
            "flow_net_5d": rows[i]["flow"],
            "mom20": rows[i]["mom"],
            "fwd": rets[i],
        }
        for i in order[:10]
    ]
    
    imp_str = "  ".join(f"{k}:{v:.3f}" for k, v in importances.items())

    lines = [
        f"as_of={as_of}  n={len(rows)}  window_flow=5d  horizon=5d",
        f"{model} rank IC: {ic_learned:+.3f}",
        f"{model} feat imp: {imp_str}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
    lines.append("")
    lines.append(f"Top {model} names:")
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:+.3f}  "
            f"net5d={t['flow_net_5d']:.3g}  mom20={t['mom20']:+.2%}  "
            f"fwd={t['fwd']:+.2%}"
        )
    lines.append("")
    lines.append(
        "Catatan: lab konsentrasi/bandar opsional — bukan klaim smart-money."
    )

    metrics = {
        **bundle,
        "as_of": as_of,
        "rank_ic_model": ic_learned,
        "model": model,
    }
    csv = ["ticker,score,flow_net_5d,mom20,fwd"] + [
        f"{t['ticker']},{t['score']:.6f},{t['flow_net_5d']:.6f},"
        f"{t['mom20']:.6f},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title=f"Broker flow · {model}",
        lines=lines,
        metrics=metrics,
        model=model,
        summary_md=(
            f"# Broker flow\n\nas_of={as_of}. {model} pada flow & momentum.\n"
            f"IC={ic_learned:.3f}.\n"
            "Bukan klaim smart-money.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench = _panel(ctx)
    
    base_model_type = "ridge"
    if "logistic" in baseline.lower():
        base_model_type = "logistic"
    elif "lgbm" in baseline.lower() or "lightgbm" in baseline.lower():
        base_model_type = "lgbm"
        
    ag_model_type = "lgbm"
    if "logistic" in against.lower():
        ag_model_type = "logistic"
    elif "ridge" in against.lower():
        ag_model_type = "ridge"
        
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
            f"# Compare broker-flow\n\n`{baseline}` vs `{against}` as_of={as_of}.\n"
        ),
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="accum / foreign-flow score components, BCI (manual review)",
        bring_back="LightGBM feature importances vs momentum",
    )
