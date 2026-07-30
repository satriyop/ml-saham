"""Ch.27 Relative strength — Mansfield RS vs IHSG benchmark momentum default."""

from __future__ import annotations

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.eval.metrics import rank_ic

META = get_meta("relative-strength")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur kekuatan relatif saham terhadap acuan IHSG.",
        "  Untuk memisahkan kenaikan harga riil dari kenaikan yang sekadar mengekor pasar.",
        "",
        "Opsi pendekatan",
        "  1) Default: LSTM / ML on relative returns",
        "  2) Baseline (compare): simple momentum ratio (Mansfield RS)",
        "",
        "Caveat",
        "  • Sering kali saham ber-RS tinggi mengalami profit taking mendadak",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline rs --against ml",
    ]
    if verbose:
        lines.append("\nDetail: strategies/rs-momentum di ai-saham.")
    return "\n".join(lines)

def _panel(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        candles = load_candles(conn, [*uni, "IHSG"], end=as_of)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    by_t: dict[str, list[tuple[str, float]]] = {}
    for r in candles:
        by_t.setdefault(r["ticker"], []).append((r["date"], float(r["close"])))

    ihsg_series = sorted(by_t.get("IHSG", []), key=lambda x: x[0])
    if len(ihsg_series) < 55:
        raise ChapterDataError("History IHSG tidak cukup (butuh >= 55 bar).")

    ihsg_dates = [d for d, _ in ihsg_series]
    ihsg_closes = [c for _, c in ihsg_series]

    rows = []
    for t in uni:
        if t == "IHSG" or t not in by_t or t not in fwd:
            continue
        series = sorted(by_t[t], key=lambda x: x[0])
        if len(series) < 55:
            continue

        t_dict = dict(series)
        ratios = []
        for d, c_idx in zip(ihsg_dates[-55:], ihsg_closes[-55:], strict=True):
            if d in t_dict and c_idx > 0:
                ratios.append(t_dict[d] / c_idx)
            else:
                ratios.append(0.0)

        if 0.0 in ratios:
            continue

        sma50_ratio = sum(ratios[-50:]) / 50.0
        if sma50_ratio > 0:
            mansfield = ((ratios[-1] / sma50_ratio) - 1.0) * 100.0
            
            seq = []
            for i in range(50, 55):
                seq.append(((ratios[i] / (sum(ratios[i-50:i])/50.0)) - 1.0) * 100.0)
                
            rows.append({
                "ticker": t,
                "rs_mansfield": mansfield,
                "rs_seq": seq,
                "fwd": fwd[t]
            })

    if len(rows) < 10:
        raise ChapterDataError(f"Panel RS terlalu kecil (n={len(rows)}).")

    return as_of, rows, bench

def _baseline_scores(rows: list[dict]) -> list[float]:
    return [r["rs_mansfield"] for r in rows]

def _against_scores(rows: list[dict]) -> tuple[list[float], str]:
    try:
        import numpy as np
        from sklearn.neural_network import MLPRegressor
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    X = np.array([r["rs_seq"] for r in rows])
    y = np.array([r["fwd"] for r in rows])
    
    # MLP as ML on relative returns (representing default LSTM / ML)
    model = MLPRegressor(hidden_layer_sizes=(10, 5), max_iter=500, random_state=42)
    model.fit(X, y)
    scores = model.predict(X).tolist()
    
    return scores, "ml_sota"

def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench = _panel(ctx)
    
    scores, model_name = _against_scores(rows)
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": rows[i]["ticker"], "score": scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(rows)}  benchmark=IHSG",
        f"Default ML RS Rank IC vs 5d fwd return: {ic:+.3f}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d return: {bench:+.2%}")

    lines.extend([
        "",
        "Top Default ML Relative Strength names vs IHSG:",
    ])

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} default_score={t['score']:+6.4f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(rows),
        "rank_ic_against": ic,
        "benchmark_return": bench,
    }
    return DemoResult(
        title="Relative strength · Default ML on relative returns",
        lines=lines,
        metrics=metrics,
        model=model_name,
        summary_md=f"# Relative strength\n\nRank IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench = _panel(ctx)
    
    base_scores = _baseline_scores(rows)
    if "ml" in baseline:
        base_scores, _ = _against_scores(rows)
        
    ag_scores = _baseline_scores(rows)
    model_against = "rs"
    if "ml" in against:
        ag_scores, model_against = _against_scores(rows)
        
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
        f"{baseline}: rank_ic={ic_b:+.3f}  top10={', '.join(top_b[:5])}…",
        f"{against}:  rank_ic={ic_a:+.3f}  top10={', '.join(top_a[:5])}…",
        f"overlap top10: {len(set(top_b) & set(top_a))}",
    ]
    compare = {
        "baseline": {"id": baseline, "rank_ic": ic_b, "top10": top_b},
        "against": {"id": against, "rank_ic": ic_a, "top10": top_a, "model": model_against},
        "as_of": as_of,
        "n": len(rows),
    }
    return CompareResult(
        title=f"Compare · {baseline} vs {against}",
        lines=lines,
        metrics={"rank_ic_baseline": ic_b, "rank_ic_against": ic_a, "n": len(rows)},
        compare=compare,
        model=f"{baseline}_vs_{against}",
        summary_md=(
            f"# Compare relative-strength\n\n`{baseline}` vs `{against}` as_of={as_of}.\n"
        ),
        scoreboard=True,
    )

