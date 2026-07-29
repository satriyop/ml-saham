"""Ch.1 Membersihkan harga — missing bars, spikes, adjustment mindset."""

from __future__ import annotations

import math
from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("clean-prices")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Harga OHLCV di IDX sering 'kotor': gap hari libur/halt, spike data,",
        "  dan (kadang) break karena corporate action / adjustment policy.",
        "  Model yang dilatih di data kotor belajar noise, bukan sinyal.",
        "",
        "Opsi pendekatan",
        "  1) Aturan statistik: MAD (Median Absolute Deviation) vs z-score",
        "  2) Local Outlier Factor (LOF) vs Isolation Forest (sklearn)",
        "",
        "Caveat",
        "  • Flag ≠ otomatis hapus bar — review dulu (bisa event nyata)",
        "  • Adjustment: pahami apakah close sudah adjusted di cache sumber",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Atau:    ml-saham compare {META.slug} --baseline isolation-forest",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Detail (--verbose)",
                "  • Demo memakai MAD + LOF",
                "  • Compare membandingkan IF (lama) vs LOF (baru)",
            ]
        )
    return "\n".join(lines)


def _mad_bounds(xs: list[float], k: float = 4.0) -> tuple[float, float]:
    """Robust anomaly detection using Median Absolute Deviation."""
    if not xs:
        return 0.0, 0.0
    ys = sorted(xs)
    median = ys[len(ys) // 2]
    deviations = sorted([abs(x - median) for x in xs])
    mad = deviations[len(deviations) // 2]
    if mad == 0:
        mad = 1e-8
    return median - k * mad, median + k * mad


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=25)
        if not uni:
            uni = resolve_universe(conn, limit=25)
        candles = load_candles(conn, uni)

    by_t: dict[str, list[dict]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append(row)

    flagged: list[dict] = []
    for t, rows in by_t.items():
        rows = sorted(rows, key=lambda r: r["date"])
        rets: list[float] = []
        dates_r: list[str] = []
        for i in range(1, len(rows)):
            c0 = float(rows[i - 1]["close"] or 0)
            c1 = float(rows[i]["close"] or 0)
            if c0 <= 0:
                continue
            rets.append((c1 / c0) - 1.0)
            dates_r.append(rows[i]["date"])
        
        if len(rets) < 30:
            continue
            
        lo, hi = _mad_bounds(rets, k=4.0)
        
        for d, r in zip(dates_r, rets):
            if r < lo or r > hi:
                flagged.append({
                    "ticker": t,
                    "date": d,
                    "return": r,
                    "reason": "MAD"
                })

    model_used = "MAD"
    try:
        import numpy as np
        from sklearn.neighbors import LocalOutlierFactor

        X = []
        meta = []
        for t, rows in by_t.items():
            rows = sorted(rows, key=lambda r: r["date"])
            for i in range(1, len(rows)):
                c0 = float(rows[i - 1]["close"] or 0)
                c1 = float(rows[i]["close"] or 0)
                vol = float(rows[i]["volume"] or 0)
                if c0 <= 0:
                    continue
                X.append([(c1 / c0) - 1.0, math.log1p(vol)])
                meta.append((t, rows[i]["date"]))
                
        if len(X) >= 50:
            clf = LocalOutlierFactor(n_neighbors=20, contamination=0.01)
            pred = clf.fit_predict(np.array(X))
            model_used += " + LOF"
            seen = {(f["ticker"], f["date"]) for f in flagged}
            for (t, d), p, feat in zip(meta, pred, X):
                if p == -1 and (t, d) not in seen:
                    flagged.append({
                        "ticker": t,
                        "date": d,
                        "return": feat[0],
                        "reason": "LOF"
                    })
    except ImportError:
        pass

    flagged.sort(key=lambda x: abs(x["return"]), reverse=True)
    top = flagged[:25]
    
    lines = [
        f"Universe sample: {len(by_t)} tickers",
        f"Flagged bars: {len(flagged)} (menampilkan {len(top)})",
        f"Methods: {model_used}",
        "",
    ]
    for f in top[:15]:
        lines.append(f"  {f['ticker']:<6} {f['date']}  ret={f['return']:+.3%}  {f['reason']}")
    if not flagged:
        lines.append("  (tidak ada flag ekstrem di sample — coba universe lebih besar)")

    metrics = {
        "n_tickers": len(by_t),
        "n_flagged": len(flagged),
        "methods": model_used,
    }
    
    csv_lines = ["ticker,date,return,reason"]
    for f in top:
        csv_lines.append(f"{f['ticker']},{f['date']},{f['return']:.6f},{f['reason']}")

    return DemoResult(
        title="Clean prices · Default anomaly flags (MAD/LOF)",
        lines=lines,
        metrics=metrics,
        model=model_used,
        summary_md=(
            "# Clean prices\n\n"
            f"Model: {model_used}\n"
            "Flag bukan sinyal jual-beli — review event nyata.\n"
        ),
        scoreboard=True,
        top_names=top[:20],
        extra_files={"top_names.csv": "\n".join(csv_lines) + "\n"},
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    """Compare IsolationForest (old) vs LOF (new)."""
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=25)
        candles = load_candles(conn, uni)

    by_t: dict[str, list[dict]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append(row)

    X = []
    meta = []
    for t, rows in by_t.items():
        rows = sorted(rows, key=lambda r: r["date"])
        for i in range(1, len(rows)):
            c0 = float(rows[i - 1]["close"] or 0)
            c1 = float(rows[i]["close"] or 0)
            vol = float(rows[i]["volume"] or 0)
            if c0 <= 0:
                continue
            X.append([(c1 / c0) - 1.0, math.log1p(vol)])
            meta.append((t, rows[i]["date"]))

    lines = ["Comparing IsolationForest vs LocalOutlierFactor (LOF)", ""]
    
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.neighbors import LocalOutlierFactor
        
        X_arr = np.array(X)
        if len(X_arr) < 50:
            return DemoResult("Compare", lines=["Data tidak cukup."], metrics={})

        clf_if = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
        pred_if = clf_if.fit_predict(X_arr)
        
        clf_lof = LocalOutlierFactor(n_neighbors=20, contamination=0.01)
        pred_lof = clf_lof.fit_predict(X_arr)

        if_flags = set(i for i, p in enumerate(pred_if) if p == -1)
        lof_flags = set(i for i, p in enumerate(pred_lof) if p == -1)
        
        both = if_flags & lof_flags
        only_if = if_flags - lof_flags
        only_lof = lof_flags - if_flags
        
        lines.append(f"IF Anomalies : {len(if_flags)}")
        lines.append(f"LOF Anomalies: {len(lof_flags)}")
        lines.append(f"Overlap      : {len(both)}")
        lines.append(f"Only IF      : {len(only_if)} (cenderung false positive global)")
        lines.append(f"Only LOF     : {len(only_lof)} (cenderung true local anomaly)")
        
        metrics = {
            "if_count": len(if_flags),
            "lof_count": len(lof_flags),
            "overlap": len(both),
        }
    except ImportError:
        lines.append("Sklearn tidak tersedia.")
        metrics = {}

    return DemoResult(
        title="Comparison: IF vs LOF",
        lines=lines,
        metrics=metrics,
        model="IF vs LOF",
        summary_md="# Compare",
        scoreboard=False,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="corp-action break hygiene di cache candles ai-saham",
        bring_back="habit flag MAD/LOF sebelum train model harga",
    )
