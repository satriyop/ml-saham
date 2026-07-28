"""Ch.27 Ichimoku cloud — Kumo cloud breakout classifier."""

from __future__ import annotations

import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import pick_as_of, resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("ichimoku-cloud")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Memprediksi apakah breakout harga melintasi Awan Kumo (Senkou Span A/B Ichimoku)",
        "  merupakan awal tren bullish berkelanjutan atau sekadar false breakout.",
        "",
        "Opsi pendekatan",
        "  1) Komponen Ichimoku Kinko Hyo: Tenkan (9d), Kijun (26d), Senkou A/B (52d)",
        "  2) Kumo Cloud Thickness Ratio = |Span A - Span B| / Close",
        "  3) Random Forest / GBDT Classifier Breakout Awan Kumo",
        "",
        "Caveat",
        "  • Parameter Ichimoku standar (9, 26, 52) berasal dari bursa Jepang (6 hari kerja)",
        "  • Awan tebal membutuhkan momentum volume tinggi untuk ditembus",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: plugins/indicators/ichimoku.py di ai-saham.")
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

    by_t = {}
    for r in candles:
        by_t.setdefault(r["ticker"], []).append(r)

    X_samples, y_samples = [], []
    for t, rows in by_t.items():
        if len(rows) < 60:
            continue
        rows = sorted(rows, key=lambda x: x["date"])
        highs = [float(r["high"] or r["close"]) for r in rows]
        lows = [float(r["low"] or r["close"]) for r in rows]
        closes = [float(r["close"]) for r in rows]

        for i in range(52, len(closes) - 5):
            tenkan = (max(highs[i - 9 : i]) + min(lows[i - 9 : i])) / 2.0
            kijun = (max(highs[i - 26 : i]) + min(lows[i - 26 : i])) / 2.0
            span_a = (tenkan + kijun) / 2.0
            span_b = (max(highs[i - 52 : i]) + min(lows[i - 52 : i])) / 2.0

            cloud_top = max(span_a, span_b)
            cloud_bot = min(span_a, span_b)
            cloud_thickness = (cloud_top - cloud_bot) / (closes[i] or 1.0)

            dist_kijun = (closes[i] - kijun) / (closes[i] or 1.0)
            tenkan_kijun_diff = (tenkan - kijun) / (closes[i] or 1.0)

            # Target: forward 5-day return >= +3%
            fwd_ret = (closes[i + 5] / closes[i] - 1.0)
            label = 1 if fwd_ret >= 0.03 else 0

            X_samples.append([cloud_thickness, dist_kijun, tenkan_kijun_diff])
            y_samples.append(label)

    if len(X_samples) < 50:
        raise ChapterDataError(f"Sample Ichimoku terlalu kecil (n={len(X_samples)}).")

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
        "cloud_thickness_ratio": float(rf.feature_importances_[0]),
        "kijun_distance": float(rf.feature_importances_[1]),
        "tenkan_kijun_spread": float(rf.feature_importances_[2]),
    }

    lines = [
        f"as_of={as_of}  samples={len(X_samples)}  train={len(Xtr)} test={len(Xte)}",
        f"RandomForest Kumo Breakout Accuracy: {acc:.1%}",
        f"Precision (Genuine Breakout):       {prec:.1%}",
        f"Recall (Cloud Capture Rate):        {rec:.1%}",
        "",
        "Feature Importances:",
        f"  Cloud Thickness Ratio: {importances['cloud_thickness_ratio']:.1%}",
        f"  Kijun Distance:        {importances['kijun_distance']:.1%}",
        f"  Tenkan-Kijun Spread:   {importances['tenkan_kijun_spread']:.1%}",
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
        title="Ichimoku cloud · Kumo breakout classifier",
        lines=lines,
        metrics=metrics,
        model="rf_ichimoku_kumo_cloud",
        summary_md=f"# Ichimoku cloud\n\nAccuracy={acc:.1%}. Precision={prec:.1%}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="plugins/indicators/ichimoku.py di ai-saham",
        bring_back="Kumo cloud thickness + Kijun distance breakout habit",
    )
