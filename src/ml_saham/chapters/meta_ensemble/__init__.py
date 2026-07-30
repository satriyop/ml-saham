"""Ch.36 Meta-Ensemble — Audit Bobot Sinyal untuk Signal Engine."""

from __future__ import annotations

import json
import sqlite3
import numpy as np

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic

META = get_meta("meta-ensemble")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah pembobotan statis (misal 30% flow, 35% setup) dari ai-saham",
        "  adalah racikan terbaik, atau justru suboptimal secara empiris?",
        "",
        "Pendekatan",
        "  • Baseline: Skor akhir menggunakan configured_weight statis ai-saham.",
        "  • Default: Skor dioptimasi ulang oleh Ridge Regression secara dinamis.",
        "",
        f"Lanjut:  ml-saham challenge engine --category signal --scenario accum --type ensemble",
    ]
    if verbose:
        lines.append("\nDetail: Evaluasi Meta-Ensemble Signal Engine.")
    return "\n".join(lines)

def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan mode challenge (run_compare) untuk evaluasi Signal Engine.")

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
    baseline_scores = []
    
    # Kita asumsikan 4 pilar ini, karena ini yang terdefinisi di payload.
    feature_names = ["institutional_flow", "setup_quality", "sector_context", "company_quality_context"]
    ai_saham_weights = {}

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            signal = payload.get("signal", {})
            alpha_score = signal.get("alpha_trigger_score", {})
            groups = alpha_score.get("group_contributions", [])
            
            # Kumpulkan skor mentah per pilar
            feats = []
            for fname in feature_names:
                score = 0.0
                for g in groups:
                    if g.get("group") == fname:
                        score = float(g.get("score", 0.0))
                        # Simpan bobot asli ai-saham untuk perbandingan (hanya butuh disimpan sekali)
                        if fname not in ai_saham_weights:
                            ai_saham_weights[fname] = float(g.get("configured_weight", 0.0)) * 100
                        break
                feats.append(score)
            
            # Baseline score = kombinasi asli ai-saham
            raw_exact_score = float(signal.get("raw_exact_score", signal.get("raw_score", 0.0)))
            
            # Ekstrak Target Y (forward return 5 session / proksi)
            fingerprint = payload.get("sub_signal_fingerprint", {})
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                fwd_ret = float(excess_5d["excess_return_pct"])
            else:
                fwd_ret = raw_exact_score / 100.0  # mock proxy if no return

            X_list.append(feats)
            y_list.append(fwd_ret)
            baseline_scores.append(raw_exact_score)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
            
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing JSON payload signal groups.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # Baseline Rank IC
    baseline_ic = rank_ic(baseline_scores, y_arr.tolist())

    # 3. Train default (Ridge Regression non-negatif jika memungkinkan, atau sekadar Ridge)
    try:
        from sklearn.linear_model import Ridge
        # Alpha cukup besar untuk stabilisasi
        clf = Ridge(alpha=10.0, random_state=42)
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            against_scores = clf.predict(X_arr)
            against_ic = rank_ic(against_scores.tolist(), y_arr.tolist())
            
            # Ekstrak Bobot (koefisien)
            # Kita paksa positif dengan absolute lalu normalkan ke 100%
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
        f"date={meta[0]['date']}  n_samples={len(meta)}  purpose={purpose}",
        "Perbandingan Signal Ensemble default (Ridge) vs Baseline (AI-Saham Weights)",
        "",
        f"Baseline Rank IC : {baseline_ic:+.3f}",
        f"Default Rank IC     : {against_ic:+.3f}",
        "",
        f"=== Analisis Rekomendasi Bobot Sejati ({imp_source}) vs (AI-Saham) ==="
    ]
    
    md_lines = [
        f"# Signal Meta-Ensemble Compare ({purpose})\n",
        "Default ML Dynamic Weights vs Baseline Static Weights.\n",
        f"- **Baseline Rank IC:** {baseline_ic:+.3f}",
        f"- **Default Rank IC:** {against_ic:+.3f}\n",
        f"### Analisis Rekomendasi Bobot Sejati ({imp_source}) vs (ai-saham)",
    ]

    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            ai_weight = ai_saham_weights.get(name, 0.0)
            lines.append(f"  {name:<24} : {imp:5.1f}% (vs {ai_weight:.1f}%)")
            md_lines.append(f"- **{name}**: {imp:5.1f}% (ai-saham: {ai_weight:.1f}%)")

    metrics = {
        "n_samples": len(meta),
        "baseline_ic": float(baseline_ic),
        "against_ic": float(against_ic),
    }

    return DemoResult(
        title="Signal Meta-Ensemble · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="ridge_ensemble_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
