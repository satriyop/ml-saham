"""Ch.23 Volatility squeeze — Bollinger squeeze & breakout classifier."""

from __future__ import annotations

import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import pick_as_of, resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("volatility-squeeze")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Kompresi volatilitas (Bollinger Bandwidth Squeeze) sering mendahului",
        "  pergerakan harga masif — namun banyak lonjakan volume awal yang berujung jebakan (false breakout).",
        "",
        "Opsi pendekatan",
        "  1) Bollinger Bandwidth Squeeze Ratio = (Upper - Lower) / Middle",
        "  2) Random Forest Classifier membedakan Genuine Breakout vs False Breakout",
        "  3) Feature Importances: Bandwidth, Volume Ratio, VWAP Deviation",
        "",
        "Caveat",
        "  • Squeeze bisa bertahan lama sebelum terjadi konfirmasi breakout",
        "  • Butuh stop loss ketat pada jebakan breakout",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: strategies/bb-squeeze di ai-saham.")
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
        uni = ctx.universe or resolve_universe(conn, limit=40)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        candles = load_candles(conn, uni, end=as_of)

    if not candles:
        raise ChapterDataError("Data candles kosong.")

    # Group candles by ticker
    by_t = {}
    for r in candles:
        by_t.setdefault(r["ticker"], []).append(r)

    X_samples, y_samples = [], []
    for t, rows in by_t.items():
        if len(rows) < 30:
            continue
        rows = sorted(rows, key=lambda x: x["date"])
        closes = [float(r["close"]) for r in rows]
        vols = [float(r["volume"] or 0) for r in rows]

        for i in range(20, len(closes) - 5):
            chunk_c = closes[i - 20 : i]
            mean_c = sum(chunk_c) / 20.0
            std_c = math.sqrt(sum((x - mean_c) ** 2 for x in chunk_c) / 20.0) or 1e-6

            upper = mean_c + 2.0 * std_c
            lower = mean_c - 2.0 * std_c
            bandwidth = (upper - lower) / (mean_c or 1.0)

            vol_ratio = (vols[i] + 1.0) / (sum(vols[i - 5 : i]) / 5.0 + 1.0)
            ret1 = (closes[i] / closes[i - 1] - 1.0)

            # Target: forward 5-day return >= +3% (Genuine breakout = 1, else 0)
            fwd_ret = (closes[i + 5] / closes[i] - 1.0)
            label = 1 if fwd_ret >= 0.03 else 0

            X_samples.append([bandwidth, vol_ratio, ret1])
            y_samples.append(label)

    if len(X_samples) < 50:
        raise ChapterDataError(f"Sample squeeze terlalu kecil (n={len(X_samples)}).")

    X_arr, y_arr = np.array(X_samples), np.array(y_samples)
    counts = np.bincount(y_arr) if len(y_arr) > 0 else np.array([])
    use_stratify = y_arr if len(counts) >= 2 and min(counts) >= 2 else None
    Xtr, Xte, ytr, yte = train_test_split(X_arr, y_arr, test_size=0.3, random_state=42, stratify=use_stratify)

    rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
    rf.fit(Xtr, ytr)
    preds = rf.predict(Xte)

    acc = float(accuracy_score(yte, preds))
    prec = float(precision_score(yte, preds, zero_division=0))
    rec = float(recall_score(yte, preds, zero_division=0))

    importances = {
        "bandwidth_squeeze": float(rf.feature_importances_[0]),
        "volume_surge_ratio": float(rf.feature_importances_[1]),
        "1d_price_momentum": float(rf.feature_importances_[2]),
    }

    lines = [
        f"as_of={as_of}  samples={len(X_samples)}  train={len(Xtr)} test={len(Xte)}",
        f"RandomForest Breakout Accuracy:  {acc:.1%}",
        f"Precision (Genuine Breakout):   {prec:.1%}",
        f"Recall (Breakout Capture Rate): {rec:.1%}",
        "",
        "Feature Importances:",
        f"  Bandwidth Squeeze:   {importances['bandwidth_squeeze']:.1%}",
        f"  Volume Surge Ratio:  {importances['volume_surge_ratio']:.1%}",
        f"  1D Price Momentum:   {importances['1d_price_momentum']:.1%}",
    ]

    metrics = {
        "as_of": as_of,
        "n_samples": len(X_samples),
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "feature_importances": importances,
    }
    return DemoResult(
        title="Volatility squeeze · breakout classifier",
        lines=lines,
        metrics=metrics,
        model="rf_volatility_squeeze",
        summary_md=f"# Volatility squeeze\n\nAccuracy={acc:.1%}. Precision={prec:.1%}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="strategies/bb-squeeze di ai-saham",
        bring_back="bandwidth squeeze ratio + RF breakout precision habit",
    )
