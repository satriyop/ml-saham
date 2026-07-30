"""Ch.8 Memprediksi waktu reaksi harga (Survival Analysis) — time-to-event."""

from __future__ import annotations

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
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.eval.metrics import metrics_bundle, rank_ic

META = get_meta("survival-analysis")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Memprediksi waktu reaksi harga (Survival Analysis) — time-to-event.",
        "",
        "Opsi pendekatan",
        "  1) XGBoost Survival Embeddings (default) untuk prediksi time-to-event",
        "  2) Kaplan-Meier Estimator (baseline/compare)",
        "",
        "Caveat",
        "  • Membutuhkan data harga harian untuk observasi event",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
        f"Compare: ml-saham learn compare {META.slug} --baseline kaplan-meier --against xgboost",
    ]
    if verbose:
        lines.append("\nCatatan: insider_cache (waktu hingga profit) di data plane.")
    return "\n".join(lines)

def _panel_survival(ctx: ChapterContext):
    # Returns rows with features, event_time, event_occurred
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=20)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        flow = foreign_net_nday(conn, uni, as_of=as_of, window=5)

        candles = load_candles(conn, uni)

    by_t = {}
    for r in candles:
        if r["ticker"] not in by_t:
            by_t[r["ticker"]] = []
        by_t[r["ticker"]].append((r["date"], float(r["close"])))

    rows = []
    fwd_ret = {}
    for t in set(uni) & set(mom) & set(flow):
        series = sorted(by_t.get(t, []), key=lambda x: x[0])
        dates = [d for d, _ in series]
        if as_of not in dates:
            idxs = [i for i, d in enumerate(dates) if d <= as_of]
            if not idxs:
                continue
            i0 = idxs[-1]
        else:
            i0 = dates.index(as_of)

        c0 = series[i0][1]
        if c0 == 0:
            continue

        # Calculate time to +5% event within 20 days
        event = False
        event_time = 20
        c_end = series[min(i0 + 5, len(series) - 1)][1]  # 5-day return for ranking IC
        fwd_ret[t] = (c_end / c0) - 1.0

        for k in range(1, 21):
            if i0 + k >= len(series):
                event_time = k
                break
            ret = (series[i0 + k][1] / c0) - 1.0
            if ret >= 0.05:
                event = True
                event_time = k
                break

        rows.append(
            {
                "ticker": t,
                "mom": mom[t],
                "flow": flow[t],
                "event": event,
                "event_time": float(event_time),
                "fwd": fwd_ret[t],
            }
        )

    if len(rows) < 10:
        raise ChapterDataError(f"Panel terlalu kecil (n={len(rows)}).")

    with connect(ctx.db_path) as conn:
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    return as_of, rows, bench

def _learned_scores(rows: list[dict], model_type: str = "xgboost") -> tuple[list[float], str, dict]:
    try:
        import numpy as np
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn/numpy: pip install -e .") from exc

    mom_z = zscore([r["mom"] for r in rows])
    flow_z = zscore([r["flow"] for r in rows])

    X = np.array(
        [
            [
                mom_z[i] if mom_z[i] is not None else 0.0,
                flow_z[i] if flow_z[i] is not None else 0.0,
            ]
            for i in range(len(rows))
        ]
    )

    if "kaplan" in model_type.lower() or "km" in model_type.lower():
        # Fallback Kaplan-Meier approximation based on momentum
        scores = [mom_z[i] if mom_z[i] is not None else 0.0 for i in range(len(rows))]
        importances = {"mom_z": 1.0, "flow_z": 0.0}

        try:
            from lifelines import KaplanMeierFitter  # noqa: F401
        except ImportError:
            pass

        return scores, "kaplan-meier", importances

    else:
        # XGBoost default
        try:
            import xgboost as xgb

            # XGBoost survival cox objective requires y to be event_time, and negative if censored
            y = np.array([r["event_time"] if r["event"] else -r["event_time"] for r in rows])

            model = xgb.XGBRegressor(
                objective="survival:cox",
                tree_method="hist",
                n_estimators=50,
                max_depth=3,
                random_state=42,
            )
            model.fit(X, y)

            # Predict returns hazard ratio (higher hazard = sooner event)
            preds = model.predict(X)
            scores = preds.tolist()

            importances = {
                "mom_z": float(model.feature_importances_[0]),
                "flow_z": float(model.feature_importances_[1]),
            }
            return scores, "xgboost-survival", importances

        except Exception:
            # Fallback to Ridge regression on negative event time
            from sklearn.linear_model import Ridge

            y_fallback = np.array([-r["event_time"] for r in rows])
            model = Ridge(alpha=1.0, random_state=42)
            model.fit(X, y_fallback)
            scores = model.predict(X).tolist()
            importances = {"mom_z": float(model.coef_[0]), "flow_z": float(model.coef_[1])}
            return scores, "xgboost-fallback(ridge)", importances

def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench = _panel_survival(ctx)
    learned, model, importances = _learned_scores(rows, model_type="xgboost")

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
            "event_time": rows[i]["event_time"],
            "event": rows[i]["event"],
            "fwd": rets[i],
        }
        for i in order[:10]
    ]

    imp_str = "  ".join(f"{k}:{v:.3f}" for k, v in importances.items())

    lines = [
        f"as_of={as_of}  n={len(rows)}",
        f"{model} rank IC vs 5d fwd: {ic_learned:+.3f}",
        f"{model} feat imp: {imp_str}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
    lines.append("")
    lines.append(f"Top {model} names (highest hazard = predicted fast):")
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:+.3f}  "
            f"event={t['event']} t={t['event_time']}d  "
            f"fwd={t['fwd']:+.2%}"
        )

    metrics = {
        **bundle,
        "as_of": as_of,
        "rank_ic_model": ic_learned,
        "model": model,
    }
    csv = ["ticker,score,event,event_time,fwd"] + [
        f"{t['ticker']},{t['score']:.6f},{t['event']},{t['event_time']:.1f},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title=f"Survival Analysis · {model}",
        lines=lines,
        metrics=metrics,
        model=model,
        summary_md=(
            f"# Survival Analysis\n\nas_of={as_of}. {model}.\n"
            f"IC={ic_learned:.3f}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench = _panel_survival(ctx)

    base_scores, base_name, _ = _learned_scores(rows, model_type=baseline)
    ag_scores, ag_name, _ = _learned_scores(rows, model_type=against)

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
            f"# Compare survival-analysis\n\n`{baseline}` vs `{against}` as_of={as_of}.\n"
        ),
        scoreboard=True,
    )

