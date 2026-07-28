"""Ch.28 Bandar detector — multi-window broker accumulation classifier."""

from __future__ import annotations

from collections import defaultdict

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
from ml_saham.data.phase2_read import load_bandar_detector
from ml_saham.eval.metrics import rank_ic

META = get_meta("bandar-detector")

_ACCDIST_MAP = {
    "BIG ACC": 2.0,
    "BIG ACCUMULATION": 2.0,
    "ACC": 1.0,
    "ACCUMULATION": 1.0,
    "NEUTRAL": 0.0,
    "DIST": -1.0,
    "DISTRIBUTION": -1.0,
    "BIG DIST": -2.0,
    "BIG DISTRIBUTION": -2.0,
}


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengklasifikasikan sinyal akumulasi/distribusi bandar multi-window (Top 1/3/5/10 broker)",
        "  untuk menguji apakah deteksi akumulasi bandar konsisten menghasilkan markup harga.",
        "",
        "Opsi pendekatan",
        "  1) Vektor Sinyal Multi-Window (Today, 5D, Top 1/3/5 AccDist)",
        "  2) Random Forest Classifier Prediksi Forward Continuation 5 Hari",
        "  3) Feature Importances: Buyer/Seller Count Ratio, Top1 % Volume",
        "",
        "Caveat",
        "  • Kode broker ditutup oleh bursa (IDX broker summary delay)",
        "  • Transaksi negosiasi (cross trade) dapat mengaburkan deteksi pasar reguler",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: bandar_detector di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        detector_rows = load_bandar_detector(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not detector_rows:
        raise ChapterDataError(
            "bandar_detector kosong.",
            hint="ml-saham doctor",
        )

    # Process bandar detector rows
    by_t = {}
    for r in detector_rows:
        t = r["ticker"]
        if t not in by_t and t in fwd:
            by_t[t] = r

    tickers = sorted(by_t.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel bandar_detector terlalu kecil (n={len(tickers)}).")

    X_list, y_list = [], []
    scores = []

    for t in tickers:
        r = by_t[t]
        tag_today = _ACCDIST_MAP.get(str(r.get("today_accdist") or "").upper(), 0.0)
        tag_5d = _ACCDIST_MAP.get(str(r.get("five_day_accdist") or "").upper(), 0.0)
        tag_top1 = _ACCDIST_MAP.get(str(r.get("top1_accdist") or "").upper(), 0.0)
        tag_top3 = _ACCDIST_MAP.get(str(r.get("top3_accdist") or "").upper(), 0.0)

        top1_pct = float(r.get("top1_percent") or 0.0)
        today_pct = float(r.get("today_percent") or 0.0)
        num_brokers = float(r.get("number_broker_buysell") or 1.0)

        accum_score = tag_today * 2.0 + tag_5d * 3.0 + tag_top3 * 2.0
        scores.append(accum_score)

        fwd_ret = float(fwd[t])
        label = 1 if fwd_ret > 0 else 0

        X_list.append([tag_today, tag_5d, tag_top1, tag_top3, top1_pct, today_pct, num_brokers])
        y_list.append(label)

    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    X_arr, y_arr = np.array(X_list), np.array(y_list)
    counts = np.bincount(y_arr) if len(y_arr) > 0 else np.array([])
    use_stratify = y_arr if len(counts) >= 2 and min(counts) >= 2 else None
    Xtr, Xte, ytr, yte = train_test_split(X_arr, y_arr, test_size=0.3, random_state=42, stratify=use_stratify)

    rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
    rf.fit(Xtr, ytr)
    preds = rf.predict(Xte)

    acc = float(accuracy_score(yte, preds))
    prec = float(precision_score(yte, preds, zero_division=0))

    importances = {
        "tag_5d_accdist": float(rf.feature_importances_[1]),
        "tag_top3_accdist": float(rf.feature_importances_[3]),
        "today_percent": float(rf.feature_importances_[5]),
    }

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "accum_score": scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=bandar_detector",
        f"Bandar Accumulation Rank IC vs 5d fwd return: {ic:+.3f}",
        f"RandomForest Accumulation Accuracy:           {acc:.1%}",
        f"Precision (Positive Markup Continuation):     {prec:.1%}",
        "",
        "Top Bandar Accumulation Names:",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} AccumScore={t['accum_score']:+4.1f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_bandar_accum": ic,
        "model_accuracy": acc,
        "model_precision": prec,
        "feature_importances": importances,
    }
    return DemoResult(
        title="Bandar detector · accumulation classifier",
        lines=lines,
        metrics=metrics,
        model="rf_bandar_detector",
        summary_md=f"# Bandar detector\n\nRank IC={ic:+.3f}. Accuracy={acc:.1%}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="bandar_detector di ai-saham",
        bring_back="bandar accdist tags + RF accumulation precision habit",
    )
