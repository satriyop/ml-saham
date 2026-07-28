"""Ch.4 Factor score — value, momentum, quality (+ ownership sleeve)."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    load_fundie_map,
    load_owner_map,
    maybe_haircut,
    momentum_nday,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import metrics_bundle, rank_ic

META = get_meta("factor-score")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menyusun skor silang-saham dari faktor: value, momentum, quality,",
        "  plus opsional ownership (institusi) jika shareholding ada.",
        "",
        "Definisi singkat (demo)",
        "  • value:  -z(PE)  (PE lebih rendah → skor lebih tinggi)",
        "  • momentum: z(return ~20 sesi)",
        "  • quality: z(ROE)",
        "  • ownership (soft): z(institution_pct) bila tersedia",
        "",
        "Opsi pendekatan",
        "  1) Hand blend equal-weight z-scores",
        "  2) Elastic-net / LightGBM pada faktor → forward return",
        "  3) Bandingkan equal-weight vs model (compare)",
        "",
        "Caveat",
        "  • PIT fundamentals — lihat Ch.0",
        "  • Ownership sleeve di-skip lembut jika tabel shareholding kosong",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline equal-weight --against elastic-net",
    ]
    if verbose:
        lines.append("\nDetail: deepdive boleh menyinggung cache fundamentals ai-saham.")
    return "\n".join(lines)


def _build_rows(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        fundies = load_fundie_map(conn, uni)
        owners = load_owner_map(conn, uni)
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    rows = []
    ownership_used = False
    for t in uni:
        f = fundies.get(t)
        if not f or t not in mom or t not in fwd:
            continue
        pe = f.get("pe_ratio_ttm")
        roe = f.get("roe_ttm")
        if pe is None or roe is None:
            continue
        try:
            pe_f = float(pe)
            roe_f = float(roe)
        except (TypeError, ValueError):
            continue
        if pe_f <= 0:
            continue
        inst = None
        ow = owners.get(t)
        if ow and ow.get("institution_pct") is not None:
            try:
                inst = float(ow["institution_pct"])
                ownership_used = True
            except (TypeError, ValueError):
                inst = None
        rows.append(
            {
                "ticker": t,
                "pe": pe_f,
                "roe": roe_f,
                "mom": float(mom[t]),
                "inst": inst,
                "fwd": float(fwd[t]),
            }
        )
    return as_of, rows, bench, ownership_used


def _factor_matrix(rows: list[dict], *, use_ownership: bool):
    pe_z = zscore([r["pe"] for r in rows])
    # value = -z(PE)
    value = [(-z if z is not None else None) for z in pe_z]
    mom_z = zscore([r["mom"] for r in rows])
    roe_z = zscore([r["roe"] for r in rows])
    inst_z = (
        zscore([r["inst"] for r in rows])
        if use_ownership and any(r["inst"] is not None for r in rows)
        else [None] * len(rows)
    )
    hand = []
    X = []
    for i in range(len(rows)):
        parts = [value[i], mom_z[i], roe_z[i]]
        if use_ownership and inst_z[i] is not None:
            parts.append(inst_z[i])
        cleaned = [0.0 if p is None else float(p) for p in parts]
        hand.append(sum(cleaned) / len(cleaned))
        X.append(cleaned[: 4 if use_ownership else 3])
        # pad to consistent width
        while len(X[-1]) < (4 if use_ownership else 3):
            X[-1].append(0.0)
    return hand, X


def _elastic_scores(X: list[list[float]], y: list[float]) -> tuple[list[float], str, list[float]]:
    try:
        import numpy as np
        from sklearn.linear_model import ElasticNet, Ridge
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc
    arr = np.array(X, dtype=float)
    yy = np.array(y, dtype=float)
    model = ElasticNet(alpha=0.01, l1_ratio=0.3, random_state=42, max_iter=10000)
    model.fit(arr, yy)
    pred = model.predict(arr)
    if float(np.std(pred)) < 1e-12:
        ridge = Ridge(alpha=1.0, random_state=42)
        ridge.fit(arr, yy)
        pred = ridge.predict(arr)
        return pred.tolist(), "ridge-fallback", ridge.coef_.tolist()
    return pred.tolist(), "elastic-net", model.coef_.tolist()


def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows, bench, ownership_used = _build_rows(ctx)
    if len(rows) < 12:
        raise ChapterDataError(f"Panel faktor terlalu kecil (n={len(rows)}).")
    hand, X = _factor_matrix(rows, use_ownership=ownership_used)
    rets_raw = [r["fwd"] for r in rows]
    rets = maybe_haircut(rets_raw, with_costs=ctx.with_costs)
    model_scores, model_name, coefs = _elastic_scores(X, rets)
    ic_hand = rank_ic(hand, rets)
    ic_model = rank_ic(model_scores, rets)
    bundle = metrics_bundle(
        model_scores,
        rets,
        benchmark_return=bench,
        date_range=(as_of, as_of),
        n_tickers=len(rows),
    )
    order = sorted(range(len(rows)), key=lambda i: model_scores[i], reverse=True)
    top = [
        {
            "ticker": rows[i]["ticker"],
            "score": model_scores[i],
            "hand": hand[i],
            "fwd": rets[i],
        }
        for i in order[:10]
    ]

    feature_names = ["value", "mom", "quality"] + (["ownership"] if ownership_used else [])
    coef_str = ", ".join(f"{name}:{c:+.4f}" for name, c in zip(feature_names, coefs, strict=False))

    lines = [
        f"as_of={as_of}  n={len(rows)}  horizon=5d",
        f"Ownership sleeve: {'aktif' if ownership_used else 'skip (soft / data tipis)'}",
        f"Hand equal-weight rank IC: {ic_hand:+.3f}",
        f"Elastic-net rank IC:       {ic_model:+.3f}",
        f"Feature weights (coefs):   {coef_str}",
        "Catatan: skor model fit in-sample pada as_of panel — bukan walk-forward.",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
        top_mean = sum(t["fwd"] for t in top[: max(1, len(rows) // 5)]) / max(
            1, min(len(top), max(1, len(rows) // 5))
        )
        lines.append(f"Top-quantile sample mean fwd: {top_mean:+.2%}  vs IHSG")
    lines.append("")
    lines.append("Top elastic-net names:")
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:+.3f}  "
            f"hand={t['hand']:+.3f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        **bundle,
        "as_of": as_of,
        "rank_ic_hand": ic_hand,
        "rank_ic_model": ic_model,
        "ownership_used": ownership_used,
        "model": model_name,
        "feature_coefs": dict(zip(feature_names, coefs, strict=False)),
    }
    csv = ["ticker,score,hand,fwd"] + [
        f"{t['ticker']},{t['score']:.6f},{t['hand']:.6f},{t['fwd']:.6f}" for t in top
    ]
    return DemoResult(
        title="Factor score · hand vs elastic-net",
        lines=lines,
        metrics=metrics,
        model=model_name,
        summary_md=(
            f"# Factor score\n\nas_of={as_of}. value/momentum/quality "
            f"(+ ownership={'on' if ownership_used else 'off'}).\n"
            f"Hand IC={ic_hand:.3f}, elastic-net IC={ic_model:.3f}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows, bench, ownership_used = _build_rows(ctx)
    hand, X = _factor_matrix(rows, use_ownership=ownership_used)
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    model_scores, model_name, _ = _elastic_scores(X, rets)
    base = hand if "equal" in baseline or baseline == "hand" else model_scores
    ag = model_scores if "elastic" in against or "model" in against else hand
    ic_b = rank_ic(base, rets)
    ic_a = rank_ic(ag, rets)
    top_b = [
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: base[i], reverse=True)[:10]
    ]
    top_a = [
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: ag[i], reverse=True)[:10]
    ]
    lines = [
        f"as_of={as_of}  n={len(rows)}",
        f"{baseline}: rank_ic={ic_b:+.3f}",
        f"{against}:  rank_ic={ic_a:+.3f} ({model_name})",
        f"overlap top10: {len(set(top_b) & set(top_a))}",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd: {bench:+.2%}")
    compare = {
        "baseline": {"id": baseline, "rank_ic": ic_b, "top10": top_b},
        "against": {"id": against, "rank_ic": ic_a, "top10": top_a},
        "as_of": as_of,
        "ownership_used": ownership_used,
        "benchmark_return": bench,
    }
    return CompareResult(
        title=f"Compare · {baseline} vs {against}",
        lines=lines,
        metrics={"rank_ic_baseline": ic_b, "rank_ic_against": ic_a, "n": len(rows)},
        compare=compare,
        model=f"{baseline}_vs_{against}",
        summary_md=f"# Compare factor-score\n\n`{baseline}` vs `{against}`.\n",
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="fundamentals / shareholding caches di ai-saham",
        bring_back="z-score factor blend + rank IC vs IHSG habit",
    )
