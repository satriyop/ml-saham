"""Ch.12 Market Regime — Regime Audit for Market Context Engine."""

from __future__ import annotations

import json
import sqlite3
import numpy as np
from datetime import datetime

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic

META = get_meta("market-regime")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah label Market Regime ai-saham (STRESSED, BULL, NEUTRAL)",
        "  benar-benar memprediksi kejatuhan (crash) IHSG di minggu berikutnya?",
        "",
        "Pendekatan",
        "  • Baseline: Klasifikasi rezim kaku dari ai-saham (market_context_snapshots).",
        "  • Default: Machine Learning (Random Forest) mengolah data mentah VIX, EIDO, USD/IDR, dll.",
        "",
        f"Lanjut:  ml-saham challenge engine --category market --type regime",
    ]
    if verbose:
        lines.append("\nDetail: Evaluasi Market Regime.")
    return "\n".join(lines)

def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan mode challenge (run_compare) untuk evaluasi Market Regime.")

def run_compare(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # Ambil data market context
        cursor = conn.execute(
            "SELECT as_of_date, regime, factors_json FROM market_context_snapshots ORDER BY as_of_date DESC LIMIT 2000"
        )
        rows = cursor.fetchall()

        # Ambil IHSG close price untuk melabeli actual market crash
        ihsg_cursor = conn.execute(
            "SELECT date, close FROM candles WHERE ticker='IHSG' ORDER BY date ASC"
        )
        ihsg_rows = ihsg_cursor.fetchall()

    if not rows:
        raise ChapterDataError("Tabel market_context_snapshots kosong.")
    if not ihsg_rows:
        raise ChapterDataError("Tidak ada data IHSG di tabel candles.")

    # 1. Map IHSG data
    ihsg_dates = [r["date"] for r in ihsg_rows]
    ihsg_closes = [float(r["close"]) for r in ihsg_rows]
    
    # 2. Siapkan dataset
    X_list = []
    y_list = []
    meta = []
    baseline_is_stressed = []

    feature_names = ["vix", "eido", "usd_idr", "idx_trend", "idx_breadth", "foreign_flow"]

    for row in rows:
        as_of = row["as_of_date"]
        regime = row["regime"]
        
        try:
            factors = json.loads(row["factors_json"])
            # Ubah array of dict menjadi dict key-value
            feat_dict = {f["name"]: float(f["value"]) if f.get("value") is not None else 0.0 for f in factors}
        except Exception:
            feat_dict = {}
            
        feats = [feat_dict.get(fname, 0.0) for fname in feature_names]
        
        # Baseline: ai-saham mendeteksi market STRESSED atau CRASH
        is_stressed = 1.0 if regime in ["STRESSED", "CRASH"] else 0.0
        
        # Hitung Actual Forward Return 5 Hari
        try:
            i0 = ihsg_dates.index(as_of)
            i1 = i0 + 5
            if i1 < len(ihsg_dates) and ihsg_closes[i0] > 0:
                fwd_ret = (ihsg_closes[i1] / ihsg_closes[i0]) - 1.0
            else:
                continue # data masa depan belum ada
        except ValueError:
            continue
            
        # Target: Apakah IHSG beneran crash? (turun > 1.0% dalam 5 hari)
        actual_crash = 1 if fwd_ret < -0.01 else 0

        X_list.append(feats)
        y_list.append(actual_crash)
        baseline_is_stressed.append(is_stressed)
        
        meta.append({
            "date": as_of,
            "fwd_ret": fwd_ret
        })

    if not X_list:
        raise ChapterDataError("Data tidak cukup untuk komparasi (mungkin history forward return belum terjadi).")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # Hitung baseline akurasi
    baseline_tp = sum(1 for b, y in zip(baseline_is_stressed, y_arr) if b == 1 and y == 1)
    baseline_fp = sum(1 for b, y in zip(baseline_is_stressed, y_arr) if b == 1 and y == 0)
    baseline_tn = sum(1 for b, y in zip(baseline_is_stressed, y_arr) if b == 0 and y == 0)
    baseline_fn = sum(1 for b, y in zip(baseline_is_stressed, y_arr) if b == 0 and y == 1)
    
    baseline_acc = (baseline_tp + baseline_tn) / len(y_arr) if len(y_arr) > 0 else 0
    baseline_precision = baseline_tp / (baseline_tp + baseline_fp) if (baseline_tp + baseline_fp) > 0 else 0
    baseline_recall = baseline_tp / (baseline_tp + baseline_fn) if (baseline_tp + baseline_fn) > 0 else 0

    # 3. Train default (Random Forest)
    try:
        from sklearn.ensemble import RandomForestClassifier
        clf = RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42, class_weight='balanced')
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            against_preds = clf.predict(X_arr)
            importances = clf.feature_importances_ * 100
            imp_source = "RF Imp"
        else:
            against_preds = np.zeros_like(y_arr)
            importances = np.zeros(len(feature_names))
            imp_source = "None"
            
    except ImportError:
        against_preds = np.zeros_like(y_arr)
        importances = np.zeros(len(feature_names))
        imp_source = "None"

    against_tp = sum(1 for s, y in zip(against_preds, y_arr) if s == 1 and y == 1)
    against_fp = sum(1 for s, y in zip(against_preds, y_arr) if s == 1 and y == 0)
    against_tn = sum(1 for s, y in zip(against_preds, y_arr) if s == 0 and y == 0)
    against_fn = sum(1 for s, y in zip(against_preds, y_arr) if s == 0 and y == 1)
    
    against_acc = (against_tp + against_tn) / len(y_arr) if len(y_arr) > 0 else 0
    against_precision = against_tp / (against_tp + against_fp) if (against_tp + against_fp) > 0 else 0
    against_recall = against_tp / (against_tp + against_fn) if (against_tp + against_fn) > 0 else 0

    lines = [
        f"n_samples={len(meta)}",
        "Perbandingan Rezim default (Random Forest) vs Baseline (AI-Saham Rule)",
        "",
        "=== Baseline (AI-Saham ASLI) ===",
        f"Accuracy  : {baseline_acc:.1%}",
        f"Precision : {baseline_precision:.1%} (Kemampuan menebak crash tanpa meleset)",
        f"Recall    : {baseline_recall:.1%} (Kemampuan menangkap SEMUA crash)",
        "",
        "=== Default (Machine Learning Dynamic Regime) ===",
        f"Accuracy  : {against_acc:.1%}",
        f"Precision : {against_precision:.1%}",
        f"Recall    : {against_recall:.1%}",
        "",
        f"=== Analisis Kontribusi Indikator Makro ({imp_source}) ==="
    ]
    
    md_lines = [
        f"# Market Regime Compare\n",
        "Default ML Dynamic Regime vs Baseline Static Rule.\n",
        f"- **Baseline Precision/Recall:** {baseline_precision:.1%} / {baseline_recall:.1%}",
        f"- **Default Precision/Recall:** {against_precision:.1%} / {against_recall:.1%}\n",
        f"### Analisis Kontribusi Indikator Makro ({imp_source})",
    ]

    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            lines.append(f"  {name:<24} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    metrics = {
        "n_samples": len(meta),
        "baseline_accuracy": float(baseline_acc),
        "against_accuracy": float(against_acc),
    }

    return DemoResult(
        title="Market Regime · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="randomforest_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
