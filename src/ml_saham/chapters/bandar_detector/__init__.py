"""Ch.31 Bandar detector — multi-window broker accumulation classifier."""

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
        "  Mendeteksi anomali aliran broker (bandar) untuk menemukan sinyal akumulasi yang tidak wajar.",
        "  Default: Menggunakan Isolation Forest pada data broker flow.",
        "  Baseline (compare): Menggunakan naive net volume (persentase net hari ini).",
        "",
        "Opsi pendekatan",
        "  1) Default (Isolation Forest): Mendeteksi outlier pada distribusi persentase volume top broker.",
        "  2) Baseline (Naive Net Volume): Menggunakan persentase net volume sederhana.",
        "",
        "Caveat",
        "  • Kode broker ditutup oleh bursa (IDX broker summary delay)",
        "  • Transaksi negosiasi (cross trade) dapat mengaburkan deteksi pasar reguler",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: bandar_detector di ai-saham.")
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

        detector_rows = load_bandar_detector(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)

    if not detector_rows:
        raise ChapterDataError(
            "bandar_detector kosong.",
            hint="ml-saham doctor",
        )

    by_t = {}
    for r in detector_rows:
        t = r["ticker"]
        if t not in by_t and t in fwd:
            by_t[t] = r

    tickers = sorted(by_t.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel bandar_detector terlalu kecil (n={len(tickers)}).")

    X_list = []
    
    for t in tickers:
        r = by_t[t]
        tag_today = _ACCDIST_MAP.get(str(r.get("today_accdist") or "").upper(), 0.0)
        top1_pct = float(r.get("top1_percent") or 0.0)
        today_pct = float(r.get("today_percent") or 0.0)
        num_brokers = float(r.get("number_broker_buysell") or 1.0)
        
        # default Features
        X_list.append([tag_today, top1_pct, today_pct, num_brokers])

    X_arr = np.array(X_list)
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)

    # Default model: Isolation Forest
    iso = IsolationForest(contamination=0.1, random_state=42)
    iso.fit(X_arr)
    # Output is anomaly score (lower is more anomalous, we negate to make it positive = anomalous)
    scores_iso = -iso.score_samples(X_arr)
    
    ic = rank_ic(scores_iso.tolist(), rets)
    
    order = sorted(range(len(tickers)), key=lambda i: scores_iso[i], reverse=True)
    top = [
        {"ticker": tickers[i], "anomaly_score": scores_iso[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=bandar_detector",
        f"Isolation Forest Anomaly IC vs 5d fwd return: {ic:+.3f}",
        "",
        "Top Anomalous Accumulation Names (default):",
    ]

    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} AnomalyScore={t['anomaly_score']:+.3f}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_against": ic,
    }
    
    return DemoResult(
        title="Bandar detector · Default (Isolation Forest)",
        lines=lines,
        metrics=metrics,
        model="isolation_forest_bandar",
        summary_md=f"# Bandar detector default\n\nIsolation Forest IC={ic:+.3f}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )

def run_compare(ctx: ChapterContext) -> DemoResult:
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

        detector_rows = load_bandar_detector(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)

    if not detector_rows:
        raise ChapterDataError(
            "bandar_detector kosong.",
            hint="ml-saham doctor",
        )

    by_t = {}
    for r in detector_rows:
        t = r["ticker"]
        if t not in by_t and t in fwd:
            by_t[t] = r

    tickers = sorted(by_t.keys())
    if len(tickers) < 8:
        raise ChapterDataError(f"Panel bandar_detector terlalu kecil (n={len(tickers)}).")

    X_list = []
    scores_baseline = []
    
    for t in tickers:
        r = by_t[t]
        tag_today = _ACCDIST_MAP.get(str(r.get("today_accdist") or "").upper(), 0.0)
        top1_pct = float(r.get("top1_percent") or 0.0)
        today_pct = float(r.get("today_percent") or 0.0)
        num_brokers = float(r.get("number_broker_buysell") or 1.0)
        
        # default Features
        X_list.append([tag_today, top1_pct, today_pct, num_brokers])
        
        # Baseline: naive net volume (using today_pct)
        scores_baseline.append(today_pct)

    X_arr = np.array(X_list)
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)

    # Default model
    iso = IsolationForest(contamination=0.1, random_state=42)
    iso.fit(X_arr)
    scores_sota = -iso.score_samples(X_arr)
    
    ic_against = rank_ic(scores_sota.tolist(), rets)
    ic_baseline = rank_ic(scores_baseline, rets)

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        "",
        f"Default (Isolation Forest) Rank IC : {ic_against:+.3f}",
        f"Baseline (Naive Net Volume) IC  : {ic_baseline:+.3f}",
        "",
        "Comparison:",
    ]
    
    if ic_against > ic_baseline:
        lines.append("  Default Isolation Forest mendeteksi anomali lebih baik dari net volume.")
    else:
        lines.append("  Baseline net volume lebih stabil pada periode ini.")

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_against": ic_against,
        "rank_ic_baseline": ic_baseline,
    }
    
    return DemoResult(
        title="Bandar detector · Default vs Baseline",
        lines=lines,
        metrics=metrics,
        model="compare_bandar",
        summary_md=f"# Bandar detector Compare\n\nDefault IC={ic_against:+.3f} vs Baseline IC={ic_baseline:+.3f}.\n",
        scoreboard=False,
    )

