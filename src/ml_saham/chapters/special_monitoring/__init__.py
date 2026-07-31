"""Ch.33 Special monitoring — Gating Audit for Risk Engine."""

from __future__ import annotations

import json
import sqlite3
import numpy as np

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect

META = get_meta("special-monitoring")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah blokir mutlak (Hard Gates) seperti BandarGate dan FundamentalGate",
        "  benar-benar menyelematkan dari crash, atau hanya paranoid yang menghilangkan profit?",
        "",
        "Pendekatan",
        "  • Baseline: Blokir statis / mutlak oleh ai-saham Risk Engine.",
        "  • Default: Logistic Regression/XGBoost Classifier memprediksi Probabilitas Crash",
        "    menggunakan status gate secara adaptif.",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}\n"        f"         ml-saham learn compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: Evaluasi Gating Risk Engine.")
    return "\n".join(lines)

def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan mode challenge (run_compare) untuk evaluasi Risk Engine.")

def run_compare(ctx: ChapterContext) -> DemoResult:
    # 1. Tentukan purpose berdasarkan scenario (default: ACCUMULATION_DISCOVERY)
    purpose = "ACCUMULATION_DISCOVERY"
    if ctx.scenario == "pre-open":
        purpose = "PRE_OPEN_AUCTION_DIRECTION"

    from ml_saham.data.observation_cohort import curriculum_payload_rows

    with connect(ctx.db_path) as conn:
        rows, _ = curriculum_payload_rows(conn, purpose, limit=1000)

    if not rows:
        raise ChapterDataError(
            f"learning_observations untuk {purpose} kosong.",
            hint="Sistem AI-Saham belum mencatat observasi ini.",
        )

    # 2. Siapkan dataset
    X_list = []
    y_list = []
    meta = []
    baseline_blocked = []

    feature_names = [
        "is_bandar_blocked",
        "is_liquidity_blocked",
        "is_fundamental_blocked",
        "is_freefloat_blocked",
        "raw_signal_score"
    ]

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            trade_setup = payload.get("trade_setup", {})
            signal = payload.get("signal", {})
            
            action = trade_setup.get("action", "")
            blocking_gates = trade_setup.get("blocking_gates", [])
            
            # Ekstraksi fitur blokir
            feats = [
                1.0 if "BandarGate" in blocking_gates else 0.0,
                1.0 if "LiquidityGate" in blocking_gates else 0.0,
                1.0 if "FundamentalGate" in blocking_gates else 0.0,
                1.0 if "FreeFloatGate" in blocking_gates else 0.0,
                float(signal.get("raw_exact_score", signal.get("raw_score", 0.0)))
            ]
            
            # Baseline: Apakah diblokir oleh sistem aslinya?
            is_blocked = 1.0 if "BLOCKED" in action else 0.0
            
            # Ekstrak Target Y (forward return)
            # Jika pre-open, mungkin pakai proxy. Jika accum, pakai benchmark_excess_return
            fingerprint = payload.get("sub_signal_fingerprint", {})
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                fwd_ret = float(excess_5d["excess_return_pct"])
            else:
                fwd_ret = float(signal.get("score", 0.0)) / 100.0  # mock proxy

            # Kita asumsikan 'Crash' (y=1) jika return negatif
            is_crash = 1 if fwd_ret < 0.0 else 0
            
            X_list.append(feats)
            y_list.append(is_crash)
            baseline_blocked.append(is_blocked)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
                "fwd_ret": fwd_ret
            })
            
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing JSON payload.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # Hitung baseline akurasi blokir
    # True Positive = Sistem blokir (1) dan memang crash (1)
    # False Positive = Sistem blokir (1) padahal aman (0) - ini membunuh profit
    baseline_tp = sum(1 for b, y in zip(baseline_blocked, y_arr) if b == 1 and y == 1)
    baseline_fp = sum(1 for b, y in zip(baseline_blocked, y_arr) if b == 1 and y == 0)
    baseline_tn = sum(1 for b, y in zip(baseline_blocked, y_arr) if b == 0 and y == 0)
    baseline_fn = sum(1 for b, y in zip(baseline_blocked, y_arr) if b == 0 and y == 1)
    
    baseline_acc = (baseline_tp + baseline_tn) / len(y_arr) if len(y_arr) > 0 else 0
    baseline_precision = baseline_tp / (baseline_tp + baseline_fp) if (baseline_tp + baseline_fp) > 0 else 0

    # 3. Train default (Logistic Regression)
    try:
        from sklearn.linear_model import LogisticRegression
        clf = LogisticRegression(random_state=42, class_weight='balanced')
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            against_preds = clf.predict(X_arr)
            # Feature Importance / Koefisien
            importances = np.abs(clf.coef_[0])
            importances = (importances / importances.sum()) * 100
            imp_source = "LogReg Coef"
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

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}  purpose={purpose}",
        "Perbandingan Gating default (LogReg) vs Baseline (AI-Saham Hard Gates)",
        "",
        "=== Baseline (AI-Saham ASLI) ===",
        f"Accuracy : {baseline_acc:.1%}",
        f"Precision: {baseline_precision:.1%} (Kemampuan blokir yang benar-benar hindari crash)",
        f"False Positives: {baseline_fp} peluang profit terbuang sia-sia",
        "",
        "=== Default (Machine Learning Soft Gates) ===",
        f"Accuracy : {against_acc:.1%}",
        f"Precision: {against_precision:.1%}",
        f"False Positives: {against_fp} peluang profit terbuang sia-sia",
        "",
        f"=== Analisis Kontribusi Gate ({imp_source}) ==="
    ]
    
    md_lines = [
        f"# Risk Engine Gating Compare ({purpose})\n",
        "Default ML Soft Gates vs Baseline Hard Gates.\n",
        f"- **Baseline Precision (Keakuratan Blokir):** {baseline_precision:.1%}",
        f"- **Default Precision (Keakuratan Blokir):** {against_precision:.1%}\n",
        f"### Analisis Kontribusi Gate ({imp_source})",
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
        title="Risk Gating · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="logreg_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
