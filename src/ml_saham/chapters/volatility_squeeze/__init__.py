"""Ch.26 Volatility squeeze — Bollinger squeeze & breakout classifier."""

from __future__ import annotations

import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import pick_as_of, resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult

META = get_meta("volatility-squeeze")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Kompresi volatilitas (Squeeze) mendahului pergerakan harga masif, namun breakout seringkali palsu.",
        "",
        "Opsi pendekatan",
        "  1) Default: BB/KC Squeeze ML Predictor (ML classifier menggunakan sinyal Bollinger Bands & Keltner Channels)",
        "  2) Baseline (compare): Fixed standard deviation (volatilitas harian di bawah threshold statis)",
        "",
        "Caveat",
        "  • ML predictor bisa overfitting pada pola masa lalu.",
        "  • Squeeze butuh volume konfirmasi untuk menghindari whipsaw.",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: strategies/bb-squeeze di ai-saham.")
    return "\n".join(lines)


def _prepare_data(ctx: ChapterContext):
    from ml_saham.data.aisaham_read import connect, load_candles

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
        highs = [float(r.get("high", r["close"])) for r in rows]
        lows = [float(r.get("low", r["close"])) for r in rows]
        vols = [float(r["volume"] or 0) for r in rows]

        for i in range(20, len(closes) - 5):
            chunk_c = closes[i - 20 : i]
            mean_c = sum(chunk_c) / 20.0
            std_c = math.sqrt(sum((x - mean_c) ** 2 for x in chunk_c) / 20.0) or 1e-6

            # Bollinger Bands
            bb_upper = mean_c + 2.0 * std_c
            bb_lower = mean_c - 2.0 * std_c
            bb_bandwidth = (bb_upper - bb_lower) / mean_c

            # Keltner Channels
            trs = []
            for j in range(i - 20, i):
                if j == 0:
                    trs.append(highs[j] - lows[j])
                else:
                    tr = max(
                        highs[j] - lows[j],
                        abs(highs[j] - closes[j - 1]),
                        abs(lows[j] - closes[j - 1])
                    )
                    trs.append(tr)
            
            atr = sum(trs) / 20.0 or 1e-6
            kc_upper = mean_c + 1.5 * atr
            kc_lower = mean_c - 1.5 * atr
            kc_bandwidth = (kc_upper - kc_lower) / mean_c

            # Squeeze Condition (BB inside KC)
            squeeze_on = 1 if (bb_upper < kc_upper and bb_lower > kc_lower) else 0

            bb_kc_ratio = bb_bandwidth / kc_bandwidth

            vol_ratio = (vols[i] + 1.0) / (sum(vols[i - 5 : i]) / 5.0 + 1.0)
            ret1 = (closes[i] / closes[i - 1] - 1.0)

            # Target: forward 5-day return >= +3% (Genuine breakout = 1, else 0)
            fwd_ret = (closes[i + 5] / closes[i] - 1.0)
            label = 1 if fwd_ret >= 0.03 else 0

            # X = [bb_bandwidth, kc_bandwidth, bb_kc_ratio, squeeze_on, vol_ratio, ret1, std_c_pct]
            std_c_pct = std_c / mean_c
            X_samples.append([bb_bandwidth, kc_bandwidth, bb_kc_ratio, squeeze_on, vol_ratio, ret1, std_c_pct])
            y_samples.append(label)

    if len(X_samples) < 50:
        raise ChapterDataError(f"Sample squeeze terlalu kecil (n={len(X_samples)}).")

    return X_samples, y_samples, as_of


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        import lightgbm as lgb
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn & lightgbm: pip install -e .") from exc

    X_samples, y_samples, as_of = _prepare_data(ctx)

    X_arr, y_arr = np.array(X_samples), np.array(y_samples)
    counts = np.bincount(y_arr) if len(y_arr) > 0 else np.array([])
    use_stratify = y_arr if len(counts) >= 2 and min(counts) >= 2 else None
    
    Xtr, Xte, ytr, yte = train_test_split(X_arr, y_arr, test_size=0.3, random_state=42, stratify=use_stratify)

    lgb_clf = lgb.LGBMClassifier(n_estimators=50, max_depth=4, random_state=42, verbose=-1)
    lgb_clf.fit(Xtr, ytr)
    preds = lgb_clf.predict(Xte)

    acc = float(accuracy_score(yte, preds))
    prec = float(precision_score(yte, preds, zero_division=0))
    rec = float(recall_score(yte, preds, zero_division=0))

    importances = lgb_clf.feature_importances_
    # X = [bb_bandwidth, kc_bandwidth, bb_kc_ratio, squeeze_on, vol_ratio, ret1, std_c_pct]
    feat_names = ["BB Bandwidth", "KC Bandwidth", "BB/KC Ratio", "Squeeze On", "Vol Ratio", "1D Return", "Std Pct"]
    imp_dict = {name: float(val) for name, val in zip(feat_names, importances)}
    # Sort importances
    sorted_imp = sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"as_of={as_of}  samples={len(X_samples)}  train={len(Xtr)} test={len(Xte)}",
        f"Default BB/KC Squeeze LightGBM Accuracy:  {acc:.1%}",
        f"Precision (Genuine Breakout):           {prec:.1%}",
        f"Recall (Breakout Capture Rate):         {rec:.1%}",
        "",
        "Feature Importances:"
    ]
    for name, val in sorted_imp:
        lines.append(f"  {name}: {val}")

    metrics = {
        "as_of": as_of,
        "n_samples": len(X_samples),
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "feature_importances": imp_dict,
    }
    return DemoResult(
        title="Volatility squeeze · Default BB/KC ML Predictor",
        lines=lines,
        metrics=metrics,
        model="default_bb_kc_squeeze_lgb",
        summary_md=f"# Volatility squeeze (default)\n\nAccuracy={acc:.1%}. Precision={prec:.1%}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        import lightgbm as lgb
        from sklearn.metrics import accuracy_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn & lightgbm: pip install -e .") from exc

    X_samples, y_samples, as_of = _prepare_data(ctx)

    X_arr, y_arr = np.array(X_samples), np.array(y_samples)
    counts = np.bincount(y_arr) if len(y_arr) > 0 else np.array([])
    use_stratify = y_arr if len(counts) >= 2 and min(counts) >= 2 else None
    
    Xtr, Xte, ytr, yte = train_test_split(X_arr, y_arr, test_size=0.3, random_state=42, stratify=use_stratify)

    # 1. Default: LightGBM Predictor
    lgb_clf = lgb.LGBMClassifier(n_estimators=50, max_depth=4, random_state=42, verbose=-1)
    lgb_clf.fit(Xtr, ytr)
    against_preds = lgb_clf.predict(Xte)

    against_acc = float(accuracy_score(yte, against_preds))
    against_prec = float(precision_score(yte, against_preds, zero_division=0))
    against_rec = float(recall_score(yte, against_preds, zero_division=0))

    # 2. Baseline: Fixed standard deviation threshold + volume surge
    # Features: X_arr = [..., vol_ratio (idx 4), ret1 (idx 5), std_c_pct (idx 6)]
    # Baseline rule: Std Pct < 0.02 (low volatility) AND Vol Ratio > 1.2 AND ret1 > 0
    base_preds = []
    for x in Xte:
        vol_ratio = x[4]
        ret1 = x[5]
        std_pct = x[6]
        
        if std_pct < 0.02 and vol_ratio > 1.2 and ret1 > 0:
            base_preds.append(1)
        else:
            base_preds.append(0)
    
    base_preds = np.array(base_preds)
    base_acc = float(accuracy_score(yte, base_preds))
    base_prec = float(precision_score(yte, base_preds, zero_division=0))
    base_rec = float(recall_score(yte, base_preds, zero_division=0))

    lines = [
        f"as_of={as_of}  samples={len(X_samples)}  test={len(Xte)}",
        "",
        "--- Default: BB/KC Squeeze ML Predictor (LightGBM) ---",
        f"Accuracy:  {against_acc:.1%}",
        f"Precision: {against_prec:.1%}",
        f"Recall:    {against_rec:.1%}",
        "",
        "--- Baseline: Fixed Standard Deviation Rule ---",
        f"Accuracy:  {base_acc:.1%}",
        f"Precision: {base_prec:.1%}",
        f"Recall:    {base_rec:.1%}",
        "",
        "Kesimpulan: Model ML (default) menggunakan interaksi non-linear antara Bollinger Bands",
        "dan Keltner Channels, umumnya mencapai precision/recall lebih baik dibanding",
        "aturan fixed standard deviation yang kaku."
    ]

    metrics = {
        "as_of": as_of,
        "n_samples": len(X_samples),
        "against_accuracy": against_acc,
        "against_precision": against_prec,
        "base_accuracy": base_acc,
        "base_precision": base_prec,
    }
    return DemoResult(
        title="Compare: Default BB/KC Squeeze vs Baseline Fixed StdDev",
        lines=lines,
        metrics=metrics,
        model="compare_volatility_squeeze",
        summary_md=f"# Volatility squeeze (Default vs Baseline)\n\nDefault Precision={against_prec:.1%}, Baseline Precision={base_prec:.1%}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="strategies/bb-squeeze di ai-saham",
        bring_back="BB/KC Squeeze default model + LightGBM precision",
    )
