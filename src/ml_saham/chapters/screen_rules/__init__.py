"""Ch.2 Screen rules — hand rules vs learned rank."""

from __future__ import annotations

from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    load_fundie_map,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic

META = get_meta("screen-rules")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menyaring saham dengan aturan tangan (PE rendah, ROE tinggi, …)",
        "  vs membiarkan model belajar ranking dari fitur yang sama.",
        "",
        "Opsi pendekatan",
        "  1) Hand screen: threshold PE/ROE/PBV",
        "  2) Decision tree / logistic pada label 'return di atas median'",
        "  3) Bandingkan hit-list & rank IC (compare)",
        "",
        "Caveat",
        "  • Fundamentals pakai fetched_date — waspadai look-ahead (lihat Ch.0)",
        "  • Aturan tangan mudah dijelaskan; model mudah overfit pada n kecil",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline hand --against tree",
    ]
    if verbose:
        lines.append("\nDetail: deepdive boleh menyinggung risk-gate precursors (stub OK).")
    return "\n".join(lines)


def _panel(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise RuntimeError("Tidak cukup history candles untuk as_of.")
        fundies = load_fundie_map(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
    rows = []
    for t in uni:
        f = fundies.get(t)
        if not f or t not in fwd:
            continue
        pe = f.get("pe_ratio_ttm")
        roe = f.get("roe_ttm")
        pbv = f.get("pbv")
        if pe is None or roe is None:
            continue
        try:
            pe_f = float(pe)
            roe_f = float(roe)
            pbv_f = float(pbv) if pbv is not None else None
        except (TypeError, ValueError):
            continue
        if pe_f <= 0:
            continue
        rows.append(
            {
                "ticker": t,
                "pe": pe_f,
                "roe": roe_f,
                "pbv": pbv_f,
                "fwd": float(fwd[t]),
            }
        )
    return as_of, rows


def _hand_score(row: dict) -> float:
    # lower PE better, higher ROE better
    return (-row["pe"]) + 10.0 * row["roe"]


def _learned_scores(rows: list[dict]) -> tuple[list[float], str]:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:
        raise RuntimeError(
            "Butuh scikit-learn: pip install 'ml-saham[ml]' atau scikit-learn"
        ) from exc

    pe_z = zscore([r["pe"] for r in rows])
    roe_z = zscore([r["roe"] for r in rows])
    X = np.array(
        [
            [
                pe_z[i] if pe_z[i] is not None else 0.0,
                roe_z[i] if roe_z[i] is not None else 0.0,
            ]
            for i in range(len(rows))
        ]
    )
    y_ret = [r["fwd"] for r in rows]
    med = sorted(y_ret)[len(y_ret) // 2]
    y = np.array([1 if r >= med else 0 for r in y_ret])
    if len(set(y.tolist())) < 2:
        # fallback: tree on regression ranks via PE/ROE only
        scores = [float(-r["pe"] + 5 * r["roe"]) for r in rows]
        return scores, "hand-fallback"

    tree = DecisionTreeClassifier(max_depth=3, random_state=42)
    tree.fit(X, y)
    # probability of positive class as score
    if hasattr(tree, "predict_proba"):
        scores = tree.predict_proba(X)[:, 1].tolist()
    else:
        scores = tree.predict(X).astype(float).tolist()
    # also fit logistic for compare path
    _ = LogisticRegression(max_iter=200)
    return scores, "decision_tree"


def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, rows = _panel(ctx)
    if len(rows) < 10:
        raise RuntimeError(
            f"Panel terlalu kecil (n={len(rows)}). Cek fundamentals + candles."
        )
    hand = [_hand_score(r) for r in rows]
    learned, model = _learned_scores(rows)
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    ic_hand = rank_ic(hand, rets)
    ic_learned = rank_ic(learned, rets)

    order = sorted(range(len(rows)), key=lambda i: learned[i], reverse=True)
    top = [
        {
            "ticker": rows[i]["ticker"],
            "score": learned[i],
            "fwd": rets[i],
            "pe": rows[i]["pe"],
            "roe": rows[i]["roe"],
        }
        for i in order[:10]
    ]
    hand_hits = {
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: hand[i], reverse=True)[:10]
    }
    model_hits = {t["ticker"] for t in top}
    overlap = sorted(hand_hits & model_hits)

    lines = [
        f"as_of={as_of}  n={len(rows)}  horizon=5d",
        f"Hand rank IC:    {ic_hand:+.3f}",
        f"Tree rank IC:    {ic_learned:+.3f}  ({model})",
        f"Top-10 overlap hand∩tree: {len(overlap)}  {', '.join(overlap) or '—'}",
        "Catatan: IC tree di sini in-sample — Ch.12 untuk walk-forward jujur.",
        "",
        "Top tree names:",
    ]
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:.3f}  "
            f"fwd={t['fwd']:+.2%}  PE={t['pe']:.1f} ROE={t['roe']:.2f}"
        )

    metrics = {
        "as_of": as_of,
        "n": len(rows),
        "rank_ic_hand": ic_hand,
        "rank_ic_tree": ic_learned,
        "overlap_top10": len(overlap),
        "n_tickers": len(rows),
    }
    csv = ["ticker,score,fwd,pe,roe"] + [
        f"{t['ticker']},{t['score']:.6f},{t['fwd']:.6f},{t['pe']:.4f},{t['roe']:.4f}"
        for t in top
    ]
    return DemoResult(
        title="Screen rules · hand vs tree",
        lines=lines,
        metrics=metrics,
        model=model,
        summary_md=(
            "# Screen rules\n\n"
            f"as_of={as_of}. Hand score vs decision tree pada PE/ROE.\n\n"
            "## Caveat\n\n- Bukan saran trading / investasi.\n"
            "- Label median-split mudah bocor jika as_of tidak disiplin.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, rows = _panel(ctx)
    hand = [_hand_score(r) for r in rows]
    learned, model = _learned_scores(rows)
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    base_scores = hand if baseline.startswith("hand") else learned
    ag_scores = learned if "tree" in against or against == "logistic" else hand
    if against == "hand":
        ag_scores = hand
    ic_b = rank_ic(base_scores, rets)
    ic_a = rank_ic(ag_scores, rets)
    top_b = [
        rows[i]["ticker"]
        for i in sorted(range(len(rows)), key=lambda i: base_scores[i], reverse=True)[
            :10
        ]
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
        "against": {"id": against, "rank_ic": ic_a, "top10": top_a, "model": model},
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
            f"# Compare screen-rules\n\n`{baseline}` vs `{against}` as_of={as_of}.\n"
        ),
        scoreboard=True,
    )
