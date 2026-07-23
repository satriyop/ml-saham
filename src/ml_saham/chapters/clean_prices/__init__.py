"""Ch.1 Membersihkan harga — missing bars, spikes, adjustment mindset."""

from __future__ import annotations

import math
from collections import defaultdict

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
        "  1) Aturan statistik: z-score / IQR pada return harian & volume",
        "  2) Isolation Forest / LOF pada fitur return+volume (sklearn)",
        "  3) Change-point (lanjutan) untuk break struktural",
        "",
        "Caveat",
        "  • Flag ≠ otomatis hapus bar — review dulu (bisa event nyata)",
        "  • Adjustment: pahami apakah close sudah adjusted di cache sumber",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Detail (--verbose)",
                "  • Demo memakai z-score/IQR + Isolation Forest bila sklearn ada",
                "  • Deep-dive opsional: higiene corp-action di cache ai-saham",
            ]
        )
    return "\n".join(lines)


def _iqr_bounds(xs: list[float], k: float = 1.5) -> tuple[float, float]:
    ys = sorted(xs)
    n = len(ys)
    q1 = ys[n // 4]
    q3 = ys[(3 * n) // 4]
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


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
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        std = math.sqrt(var) if var > 0 else 0.0
        lo, hi = _iqr_bounds(rets)
        for d, r in zip(dates_r, rets, strict=True):
            z = (r - mean) / std if std > 0 else 0.0
            reasons = []
            if abs(z) >= 4.0:
                reasons.append(f"z={z:.1f}")
            if r < lo or r > hi:
                reasons.append("IQR")
            if reasons:
                flagged.append(
                    {
                        "ticker": t,
                        "date": d,
                        "return": r,
                        "reason": "+".join(reasons),
                    }
                )

    # Isolation Forest on return features if sklearn available
    if_method = "none"
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

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
            clf = IsolationForest(
                n_estimators=100, contamination=0.01, random_state=42
            )
            pred = clf.fit_predict(np.array(X))
            if_method = "isolation_forest"
            seen = {(f["ticker"], f["date"]) for f in flagged}
            for (t, d), p, feat in zip(meta, pred, X, strict=True):
                if p == -1 and (t, d) not in seen:
                    flagged.append(
                        {
                            "ticker": t,
                            "date": d,
                            "return": feat[0],
                            "reason": "IF",
                        }
                    )
    except ImportError:
        if_method = "sklearn_missing"

    flagged.sort(key=lambda x: abs(x["return"]), reverse=True)
    top = flagged[:25]
    lines = [
        f"Universe sample: {len(by_t)} tickers",
        f"Flagged bars: {len(flagged)} (menampilkan {len(top)})",
        f"Methods: z-score|IQR + {if_method}",
        "",
    ]
    for f in top[:15]:
        lines.append(
            f"  {f['ticker']:<6} {f['date']}  ret={f['return']:+.3%}  {f['reason']}"
        )
    if not flagged:
        lines.append("  (tidak ada flag ekstrem di sample — coba universe lebih besar)")

    metrics = {
        "n_tickers": len(by_t),
        "n_flagged": len(flagged),
        "methods": ["zscore", "iqr", if_method],
        "top_flagged": top[:20],
    }
    csv_lines = ["ticker,date,return,reason"]
    for f in top:
        csv_lines.append(f"{f['ticker']},{f['date']},{f['return']:.6f},{f['reason']}")

    return DemoResult(
        title="Clean prices · anomaly flags",
        lines=lines,
        metrics=metrics,
        model=if_method,
        summary_md=(
            "# Clean prices\n\n"
            "Flag return ekstrem (z-score/IQR ± Isolation Forest).\n"
            "Flag bukan sinyal jual-beli — review event nyata.\n\n"
            "## Caveat\n\n- Bukan saran trading / investasi.\n"
        ),
        scoreboard=True,
        top_names=top[:20],
        extra_files={"top_names.csv": "\n".join(csv_lines) + "\n"},
    )
