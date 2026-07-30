"""Ch.9 Volume anomaly — how much (price/volume only)."""

from __future__ import annotations

import math
from collections import defaultdict

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
        "  1) Autoencoders (Reconstruction Loss) [default]",
        "  2) Multivariate IsolationForest [baseline/compare]",
        "",
        "Caveat",
        "  • Flag ≠ sinyal trading; bisa event korporasi / berita",
        "  • Jangan campur klaim broker/flow di chapter ini",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
        f"Atau:    ml-saham learn compare {META.slug} --baseline isolation-forest",
    ]
    if verbose:
        lines.append("\nDetail: fokus hygiene volume (tidak ada engine policy khusus).")
    return "\n".join(lines)

def _extract_features(candles: list[dict], uni: list[str]) -> tuple[dict, list, list]:
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
    return by_t, feats, meta

def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=30)
        if not uni:
            raise ChapterDataError("Universe kosong.")
        candles = load_candles(conn, uni)

    by_t, feats, meta = _extract_features(candles, uni)

    if len(feats) < 100:
        raise ChapterDataError(f"Sample volume features terlalu kecil (n={len(feats)}).")

    X = np.array(feats, dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    autoencoder = MLPRegressor(
        hidden_layer_sizes=(8, 4, 8),
        activation="relu",
        max_iter=200,
        random_state=42,
    )
    autoencoder.fit(X_scaled, X_scaled)
    reconstruction_err = np.mean((X_scaled - autoencoder.predict(X_scaled)) ** 2, axis=1)
    
    threshold = float(np.percentile(reconstruction_err, 98))
    
    flagged = []
    for (t, d, ret, vr), err in zip(meta, reconstruction_err, strict=True):
        if err > threshold:
            flagged.append(
                {
                    "ticker": t,
                    "date": d,
                    "abs_ret": ret,
                    "vol_ratio": vr,
                    "err": float(err),
                    "reason": "Autoencoder",
                }
            )

    flagged.sort(key=lambda x: x["err"], reverse=True)
    top = flagged[:25]
    lines = [
        f"Universe sample: {len(by_t)}  feature rows: {len(feats)}",
        f"Flagged: {len(flagged)} (Top 2% reconstruction error)",
        "Methods: Autoencoders (Reconstruction Loss)",
        "",
        "Top anomalies by reconstruction error:",
    ]
    for f in top[:12]:
        lines.append(
            f"  {f['ticker']:<6} {f['date']}  "
            f"|ret|={f['abs_ret']:.2%}  vol/avg={f['vol_ratio']:.1f}x  err={f['err']:.2f}"
        )

    unique_t = set(f["ticker"] for f in flagged)
    metrics = {
        "n_tickers": len(by_t),
        "n_samples": len(feats),
        "n_flagged": len(flagged),
        "flagged_tickers_count": len(unique_t),
        "top_anomalies": top[:10],
    }
    csv = ["ticker,date,abs_ret,vol_ratio,err,reason"] + [
        f"{f['ticker']},{f['date']},{f['abs_ret']:.6f},{f['vol_ratio']:.6f},{f['err']:.6f},{f['reason']}"
        for f in top
    ]
    return DemoResult(
        title="Volume anomaly · Autoencoders",
        lines=lines,
        metrics=metrics,
        model="autoencoder",
        summary_md=(
            "# Volume anomaly\n\n"
            f"Flagged {len(flagged)} price-volume anomalies across {len(unique_t)} tickers.\n"
        ),
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top[:10],
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )

def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=30)
        if not uni:
            raise ChapterDataError("Universe kosong.")
        candles = load_candles(conn, uni)

    by_t, feats, meta = _extract_features(candles, uni)

    if len(feats) < 100:
        raise ChapterDataError(f"Sample volume features terlalu kecil (n={len(feats)}).")

    X = np.array(feats, dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iforest = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
    pred_if = iforest.fit_predict(X_scaled)
    if_flags = set(i for i, p in enumerate(pred_if) if p == -1)

    autoencoder = MLPRegressor(
        hidden_layer_sizes=(8, 4, 8),
        activation="relu",
        max_iter=200,
        random_state=42,
    )
    autoencoder.fit(X_scaled, X_scaled)
    reconstruction_err = np.mean((X_scaled - autoencoder.predict(X_scaled)) ** 2, axis=1)
    threshold = float(np.percentile(reconstruction_err, 98))
    ae_flags = set(i for i, err in enumerate(reconstruction_err) if err > threshold)

    both = ae_flags & if_flags
    only_ae = ae_flags - if_flags
    only_if = if_flags - ae_flags
    
    lines = [
        "Comparing Autoencoder (default) vs IsolationForest (Baseline)",
        f"Universe sample: {len(by_t)}  feature rows: {len(feats)}",
        "",
        f"Autoencoder Anomalies : {len(ae_flags)}",
        f"IF Anomalies          : {len(if_flags)}",
        f"Overlap               : {len(both)}",
        f"Only Autoencoder      : {len(only_ae)}",
        f"Only IsolationForest  : {len(only_if)}",
    ]
    
    metrics = {
        "ae_count": len(ae_flags),
        "if_count": len(if_flags),
        "overlap": len(both),
    }

    return DemoResult(
        title="Comparison: Autoencoder vs IsolationForest",
        lines=lines,
        metrics=metrics,
        model="AE vs IF",
        summary_md="# Compare\nAutoencoder vs IsolationForest",
        scoreboard=False,
    )

