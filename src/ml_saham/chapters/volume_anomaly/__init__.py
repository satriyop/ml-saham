"""Ch.8 Volume anomaly — how much (price/volume only)."""

from __future__ import annotations

import math
from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("volume-anomaly")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Lonjakan *berapa banyak* (volume vs harga) — beda dari Ch.6 (*who*/flow)",
        "  dan Ch.1 (spike harga kotor). Di sini: anomali price–volume saja.",
        "",
        "Opsi pendekatan",
        "  1) Isolation Forest pada |return|, volume z, volume/avg",
        "  2) One-Class SVM (satu kelas 'normal')",
        "  3) Bandingkan overlap flag kedua metode",
        "",
        "Caveat",
        "  • Flag ≠ sinyal trading; bisa event korporasi / berita",
        "  • Jangan campur klaim broker/flow di chapter ini",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: tidak ada deepdive engine khusus — fokus hygiene volume.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.svm import OneClassSVM
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=30)
        if not uni:
            raise ChapterDataError("Universe kosong.")
        candles = load_candles(conn, uni)

    by_t: dict[str, list] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append(row)

    feats: list[list[float]] = []
    meta: list[tuple[str, str, float, float]] = []
    for t, rows in by_t.items():
        rows = sorted(rows, key=lambda r: r["date"])
        vols = [float(r["volume"] or 0) for r in rows]
        if len(rows) < 30:
            continue
        # rolling mean volume for z / ratio
        for i in range(20, len(rows)):
            c0 = float(rows[i - 1]["close"] or 0)
            c1 = float(rows[i]["close"] or 0)
            if c0 <= 0:
                continue
            ret = abs(c1 / c0 - 1.0)
            window = vols[i - 20 : i]
            mean_v = sum(window) / len(window)
            var_v = sum((v - mean_v) ** 2 for v in window) / len(window)
            std_v = math.sqrt(var_v) if var_v > 0 else 0.0
            v = vols[i]
            vz = (v - mean_v) / std_v if std_v > 0 else 0.0
            vratio = v / mean_v if mean_v > 0 else 0.0
            feats.append([ret, vz, vratio])
            meta.append((t, rows[i]["date"], ret, vratio))

    if len(feats) < 100:
        raise ChapterDataError(f"Sample volume features terlalu kecil (n={len(feats)}).")

    X = np.array(feats, dtype=float)
    iforest = IsolationForest(
        n_estimators=120, contamination=0.02, random_state=42
    )
    pred_if = iforest.fit_predict(X)
    ocsvm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.02)
    pred_oc = ocsvm.fit_predict(X)

    flagged = []
    both = 0
    for (t, d, ret, vr), p_if, p_oc in zip(meta, pred_if, pred_oc, strict=True):
        if p_if == -1 or p_oc == -1:
            methods = []
            if p_if == -1:
                methods.append("IF")
            if p_oc == -1:
                methods.append("OCSVM")
            if p_if == -1 and p_oc == -1:
                both += 1
            flagged.append(
                {
                    "ticker": t,
                    "date": d,
                    "abs_ret": ret,
                    "vol_ratio": vr,
                    "reason": "+".join(methods),
                }
            )

    flagged.sort(key=lambda x: x["vol_ratio"], reverse=True)
    top = flagged[:25]
    lines = [
        f"Universe sample: {len(by_t)}  feature rows: {len(feats)}",
        f"Flagged: {len(flagged)}  overlap IF∩OCSVM: {both}",
        "Methods: IsolationForest + OneClassSVM (price/volume only)",
        "",
        "Top by volume/avg20:",
    ]
    for f in top[:12]:
        lines.append(
            f"  {f['ticker']:<6} {f['date']}  "
            f"|ret|={f['abs_ret']:.2%}  vol/avg={f['vol_ratio']:.1f}x  {f['reason']}"
        )

    metrics = {
        "n_tickers": len(by_t),
        "n_rows": len(feats),
        "n_flagged": len(flagged),
        "overlap_both": both,
        "methods": ["isolation_forest", "one_class_svm"],
        "top_flagged": top[:20],
    }
    csv = ["ticker,date,abs_ret,vol_ratio,reason"] + [
        f"{f['ticker']},{f['date']},{f['abs_ret']:.6f},{f['vol_ratio']:.6f},{f['reason']}"
        for f in top
    ]
    return DemoResult(
        title="Volume anomaly · IF + One-Class SVM",
        lines=lines,
        metrics=metrics,
        model="if_ocsvm",
        summary_md=(
            "# Volume anomaly\n\n"
            "Price/volume only — bukan flow/broker. "
            f"Flagged={len(flagged)}, overlap={both}.\n"
        ),
        scoreboard=True,
        top_names=top[:20],
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="— (volume–price hygiene; pisahkan dari broker-flow)",
        bring_back="IF/OCSVM habit pada fitur volume tanpa klaim who/flow",
    )
