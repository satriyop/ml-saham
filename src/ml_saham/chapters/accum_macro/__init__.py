"""Ch.39 Accumulation Macro-Ensemble."""

from __future__ import annotations

import json
import sqlite3
import numpy as np

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic

META = get_meta("accum-macro")

def explore_text(*, verbose: bool = False) -> str:
    return f"Explore {META.title}"

def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan run_compare.")

def run_compare(ctx: ChapterContext) -> DemoResult:
    from ml_saham.data.observation_cohort import curriculum_payload_rows

    with connect(ctx.db_path) as conn:
        rows, _ = curriculum_payload_rows(conn, "ACCUMULATION_DISCOVERY", limit=1000)

    if not rows:
        raise ChapterDataError("learning_observations untuk ACCUMULATION_DISCOVERY kosong.")

    # Prepare dataset
    X_list = []
    y_list = []
    baseline_scores = []
    meta = []
    
    # 3 Makro Komponen Final Screener
    feature_names = [
        "signal_score", 
        "market_multiplier", 
        "risk_multiplier"
    ]

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            fingerprint = payload.get("sub_signal_fingerprint", {})
            signal = payload.get("signal", {})
            setup = payload.get("trade_setup", {})
            
            # Extract Makro Features
            sig_score = float(signal.get("raw_exact_score", signal.get("raw_score", 0.0)))
            mkt_mult = float(setup.get("signal_multiplier", 1.0))
            rsk_mult = float(fingerprint.get("volatility_size_multiplier_at_signal", 1.0))
            
            feats = [sig_score, mkt_mult, rsk_mult]
            X_list.append(feats)
            
            # Extract Baseline score (Biasanya Final Score = Signal * Market * Risk)
            # Karena di ai-saham ini berjenjang, kita asumsikan baseline = sig_score * mkt_mult * rsk_mult
            b_score = sig_score * mkt_mult * rsk_mult
            baseline_scores.append(b_score)
            
            # Ekstrak Target Y (forward return 5 session / proksi)
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                fwd_ret = float(excess_5d["excess_return_pct"])
            else:
                fwd_ret = sig_score / 100.0  # mock proxy
            y_list.append(fwd_ret)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing JSON payload untuk accum-macro.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # Baseline Rank IC
    baseline_ic = rank_ic(baseline_scores, y_arr.tolist())

    # Train default Macro-Ensemble (Ridge Regression)
    try:
        from sklearn.linear_model import Ridge
        clf = Ridge(alpha=10.0, random_state=42)
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            against_scores = clf.predict(X_arr)
            against_ic = rank_ic(against_scores.tolist(), y_arr.tolist())
            
            importances = np.abs(clf.coef_)
            if importances.sum() > 0:
                importances = (importances / importances.sum()) * 100
            imp_source = "Ridge Coef"
        else:
            against_ic = 0.0
            importances = np.zeros(len(feature_names))
            imp_source = "None"
    except ImportError:
        against_ic = 0.0
        importances = np.zeros(len(feature_names))
        imp_source = "None"

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}",
        "Perbandingan Screener Macro-Ensemble Default vs Baseline",
        "",
        f"Baseline Rank IC : {baseline_ic:+.3f}",
        f"Default Rank IC     : {against_ic:+.3f}",
        "",
        f"=== Analisis Bobot Pengaruh ({imp_source}) ==="
    ]
    
    md_lines = [
        f"# Screener Macro-Ensemble Compare\n",
        "Default ML Dynamic Weights vs Baseline (Signal x Market x Risk).\n",
        f"- **Baseline Rank IC:** {baseline_ic:+.3f}",
        f"- **Default Rank IC:** {against_ic:+.3f}\n",
        f"### Analisis Bobot Pengaruh Pilar Utama ({imp_source})",
    ]

    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            lines.append(f"  {name:<24} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    return DemoResult(
        title="Screener Macro-Ensemble \u00b7 Compare Asli",
        lines=lines,
        metrics={"n_samples": len(meta), "baseline_ic": float(baseline_ic), "against_ic": float(against_ic)},
        model="macro_ensemble_ridge",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
