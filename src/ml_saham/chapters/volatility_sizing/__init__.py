"""Ch.11 Volatility sizing — Sizing Audit for Risk Engine."""

from __future__ import annotations

import json
import sqlite3
import numpy as np

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic

META = get_meta("volatility-sizing")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah memotong ukuran posisi (sizing) berdasarkan volatilitas statis",
        "  menghasilkan Sharpe Ratio yang lebih baik, atau malah suboptimal?",
        "",
        "Pendekatan",
        "  • Baseline: Multiplier statis dari ai-saham (volatility_size_multiplier_at_signal).",
        "  • SOTA: Multiplier dinamis yang dioptimasi oleh Ridge Regression / Kelly",
        "    menggunakan fitur ATR dan volatilitas.",
        "",
        f"Lanjut:  ml-saham challenge engine --category risk --scenario accum --type sizing",
    ]
    if verbose:
        lines.append("\nDetail: Evaluasi Sizing Risk Engine.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan mode challenge (run_compare) untuk evaluasi Risk Engine.")


def run_compare(ctx: ChapterContext) -> DemoResult:
    # 1. Tentukan purpose berdasarkan scenario (default: ACCUMULATION_DISCOVERY)
    purpose = "ACCUMULATION_DISCOVERY"
    if ctx.scenario == "pre-open":
        purpose = "PRE_OPEN_AUCTION_DIRECTION"

    with connect(ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT decision_payload_json FROM learning_observations WHERE purpose=? ORDER BY captured_at DESC LIMIT 1000",
            (purpose,)
        )
        rows = cursor.fetchall()

    if not rows:
        raise ChapterDataError(
            f"learning_observations untuk {purpose} kosong.",
            hint="Sistem AI-Saham belum mencatat observasi ini.",
        )

    # 2. Siapkan dataset
    X_list = []
    y_list = []
    meta = []
    baseline_sizing = []

    feature_names = [
        "atr_pct_at_signal",
        "bb_width_pctile_at_signal",
        "rsi_at_signal",
        "raw_signal_score"
    ]

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            fingerprint = payload.get("sub_signal_fingerprint", {})
            signal = payload.get("signal", {})
            
            # Ekstraksi fitur
            feats = [
                float(fingerprint.get("atr_pct_at_signal", 0.0)),
                float(fingerprint.get("bb_width_pctile_at_signal", 0.0)),
                float(fingerprint.get("rsi_at_signal", 50.0)),
                float(signal.get("raw_exact_score", signal.get("raw_score", 0.0)))
            ]
            
            # Baseline sizing (fallback ke 1.0 jika tidak ada)
            base_size = float(fingerprint.get("volatility_size_multiplier_at_signal", 1.0))
            
            # Ekstrak Target Y (forward return)
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                fwd_ret = float(excess_5d["excess_return_pct"])
            else:
                fwd_ret = float(signal.get("score", 0.0)) / 100.0  # mock proxy

            X_list.append(feats)
            y_list.append(fwd_ret)
            baseline_sizing.append(base_size)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
            
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing JSON payload.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # 3. Baseline Simulation
    # Hitung mean return & stdev untuk Sharpe proksi
    baseline_returns = y_arr * np.array(baseline_sizing)
    mean_ret_base = np.mean(baseline_returns)
    std_ret_base = np.std(baseline_returns)
    if std_ret_base == 0:
        std_ret_base = 1e-9
    sharpe_base = mean_ret_base / std_ret_base

    # 4. Train SOTA (Ridge Regression)
    try:
        from sklearn.linear_model import Ridge
        clf = Ridge(alpha=1.0, random_state=42)
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            # SOTA Sizing (normalisasi ke 0.0 - 1.0)
            raw_sota = clf.predict(X_arr)
            # Simple MinMax scaling ke 0.0 - 1.0 sebagai multiplier
            min_val = np.min(raw_sota)
            max_val = np.max(raw_sota)
            if max_val > min_val:
                sota_sizing = (raw_sota - min_val) / (max_val - min_val)
            else:
                sota_sizing = np.ones_like(y_arr)
            
            importances = np.abs(clf.coef_)
            importances = (importances / importances.sum()) * 100
            imp_source = "Ridge Coef"
        else:
            sota_sizing = np.ones_like(y_arr)
            importances = np.zeros(len(feature_names))
            imp_source = "None"
            
    except ImportError:
        sota_sizing = np.ones_like(y_arr)
        importances = np.zeros(len(feature_names))
        imp_source = "None"

    sota_returns = y_arr * sota_sizing
    mean_ret_sota = np.mean(sota_returns)
    std_ret_sota = np.std(sota_returns)
    if std_ret_sota == 0:
        std_ret_sota = 1e-9
    sharpe_sota = mean_ret_sota / std_ret_sota

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}  purpose={purpose}",
        "Perbandingan Sizing SOTA (Ridge) vs Baseline (AI-Saham Statis)",
        "",
        "=== Baseline (AI-Saham ASLI) ===",
        f"Rata-rata Multiplier: {np.mean(baseline_sizing):.2f}",
        f"Sharpe Ratio Proksi : {sharpe_base:.3f}",
        "",
        "=== SOTA (Machine Learning Dynamic Sizing) ===",
        f"Rata-rata Multiplier: {np.mean(sota_sizing):.2f}",
        f"Sharpe Ratio Proksi : {sharpe_sota:.3f}",
        "",
        f"=== Analisis Kontribusi Fitur Sizing ({imp_source}) ==="
    ]
    
    md_lines = [
        f"# Risk Engine Sizing Compare ({purpose})\n",
        "SOTA ML Dynamic Sizing vs Baseline Static Multiplier.\n",
        f"- **Baseline Sharpe Proksi:** {sharpe_base:.3f}",
        f"- **SOTA Sharpe Proksi:** {sharpe_sota:.3f}\n",
        f"### Analisis Kontribusi Sizing ({imp_source})",
    ]

    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            lines.append(f"  {name:<24} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    metrics = {
        "n_samples": len(meta),
        "baseline_sharpe": float(sharpe_base),
        "sota_sharpe": float(sharpe_sota),
    }

    return DemoResult(
        title="Risk Sizing · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="ridge_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )

def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="risk engine / sizing",
        bring_back="Sizing vs ML",
    )
