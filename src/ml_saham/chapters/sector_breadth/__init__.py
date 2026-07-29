"""Ch.25 Sector breadth — market participation & sector rotation index."""

from __future__ import annotations

from collections import defaultdict
import math

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
from ml_saham.data.aisaham_read import connect, load_candles, load_sector_map
from ml_saham.eval.metrics import rank_ic

META = get_meta("sector-breadth")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Partisipasi pasar sektor (persentase saham di atas SMA-20) mengindikasikan",
        "  rotasi modal institusi lintas sektor sebelum pergerakan tren makro.",
        "",
        "Opsi pendekatan",
        "  1) SOTA (default): Advance-Decline PCA",
        "  2) Baseline (compare): equal-weight sector index",
        "",
        "Caveat",
        "  • Sektor dengan sedikit emiten bisa menunjukkan breadth ekstrim (noise)",
        "  • Rotasi sektor sering mendahului pergerakan indeks utama",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Banding: ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_sector_map + load_candles di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.decomposition import PCA
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        sector_map = load_sector_map(conn)
        candles = load_candles(conn, uni, end=as_of)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    # Group closes by ticker
    by_t: dict[str, list[float]] = defaultdict(list)
    for r in candles:
        by_t[r["ticker"]].append(float(r["close"]))

    # Filter tickers with enough history
    tickers = [t for t in uni if len(by_t[t]) >= 25 and t in fwd]
    if len(tickers) < 10:
        raise ChapterDataError(f"Panel ticker terlalu kecil (n={len(tickers)}).")

    # Compute SMA-20 and status (> SMA20) per ticker
    above_sma20: dict[str, bool] = {}
    for t in tickers:
        closes = by_t[t]
        sma20 = sum(closes[-20:]) / 20.0
        above_sma20[t] = bool(closes[-1] > sma20)

    # Aggregate breadth by sector
    sector_tickers: dict[str, list[str]] = defaultdict(list)
    for t in tickers:
        sec = sector_map.get(t, "Other")
        sector_tickers[sec].append(t)

    sector_breadth: dict[str, float] = {}
    sector_fwd: dict[str, float] = {}
    for sec, st_list in sector_tickers.items():
        if not st_list:
            continue
        n_above = sum(1 for t in st_list if above_sma20[t])
        sector_breadth[sec] = n_above / len(st_list)
        sector_fwd[sec] = sum(fwd[t] for t in st_list) / len(st_list)

    # Compute PCA Sector Breadth Factor across stocks (SOTA)
    X_stock = []
    for t in tickers:
        sec = sector_map.get(t, "Other")
        b_val = sector_breadth.get(sec, 0.5)
        is_above = 1.0 if above_sma20[t] else 0.0
        X_stock.append([b_val, is_above])

    pca = PCA(n_components=1, random_state=42)
    pca_scores = pca.fit_transform(np.array(X_stock)).flatten().tolist()
    explained_var = float(pca.explained_variance_ratio_[0])

    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(pca_scores, rets)

    # Sort sectors by breadth %
    sorted_sectors = sorted(sector_breadth.items(), key=lambda x: -x[1])

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  n_sectors={len(sector_tickers)}",
        f"SOTA (Advance-Decline PCA) explained var: {explained_var:.1%}",
        f"Sector Breadth Rank IC vs 5d fwd return:          {ic:+.3f}",
        "",
        "Sector Market Participation (> SMA-20):",
    ]
    for sec, b_pct in sorted_sectors:
        n_s = len(sector_tickers[sec])
        avg_f = sector_fwd[sec]
        lines.append(f"  {sec:<22} n={n_s:2d}  breadth={b_pct:5.1%}  fwd5d={avg_f:+.2%}")

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "n_sectors": len(sector_tickers),
        "pca_explained_var": explained_var,
        "rank_ic_sector_breadth": ic,
    }
    return DemoResult(
        title="Sector breadth · market participation index (SOTA)",
        lines=lines,
        metrics=metrics,
        model="pca_sector_breadth",
        summary_md=f"# Sector breadth\n\nRank IC={ic:+.3f}. PCA var={explained_var:.1%}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.decomposition import PCA
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        sector_map = load_sector_map(conn)
        candles = load_candles(conn, uni, end=as_of)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    # Group closes by ticker
    by_t: dict[str, list[float]] = defaultdict(list)
    for r in candles:
        by_t[r["ticker"]].append(float(r["close"]))

    # Filter tickers with enough history
    tickers = [t for t in uni if len(by_t[t]) >= 25 and t in fwd]
    if len(tickers) < 10:
        raise ChapterDataError(f"Panel ticker terlalu kecil (n={len(tickers)}).")

    # Compute SMA-20 and status (> SMA20) per ticker
    above_sma20: dict[str, bool] = {}
    for t in tickers:
        closes = by_t[t]
        sma20 = sum(closes[-20:]) / 20.0
        above_sma20[t] = bool(closes[-1] > sma20)

    # Aggregate breadth by sector
    sector_tickers: dict[str, list[str]] = defaultdict(list)
    for t in tickers:
        sec = sector_map.get(t, "Other")
        sector_tickers[sec].append(t)

    sector_breadth: dict[str, float] = {}
    for sec, st_list in sector_tickers.items():
        if not st_list:
            continue
        n_above = sum(1 for t in st_list if above_sma20[t])
        sector_breadth[sec] = n_above / len(st_list)

    X_stock = []
    baseline_scores = []
    for t in tickers:
        sec = sector_map.get(t, "Other")
        b_val = sector_breadth.get(sec, 0.5)
        is_above = 1.0 if above_sma20[t] else 0.0
        X_stock.append([b_val, is_above])
        # Baseline: equal-weight sector index proxy (using sector breadth)
        baseline_scores.append(b_val)

    # SOTA: Advance-Decline PCA
    pca = PCA(n_components=1, random_state=42)
    sota_scores = pca.fit_transform(np.array(X_stock)).flatten().tolist()
    explained_var = float(pca.explained_variance_ratio_[0])

    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic_sota = rank_ic(sota_scores, rets)
    ic_base = rank_ic(baseline_scores, rets)

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}",
        "",
        "SOTA (Advance-Decline PCA):",
        f"  Rank IC = {ic_sota:+.3f}",
        f"  Explained variance = {explained_var:.1%}",
        "",
        "Baseline (equal-weight sector index):",
        f"  Rank IC = {ic_base:+.3f}",
    ]

    metrics = {
        "ic_sota": ic_sota,
        "ic_base": ic_base,
    }
    return DemoResult(
        title="Compare: Advance-Decline PCA vs Equal-weight Sector Index",
        lines=lines,
        metrics=metrics,
        model="compare",
        summary_md=f"# Compare\n\nSOTA (PCA)={ic_sota:+.3f}, Base (Eq-W)={ic_base:+.3f}",
        scoreboard=False,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="sector_breadth script di ai-saham",
        bring_back="sector breadth % + PCA primary factor rank IC habit",
    )
