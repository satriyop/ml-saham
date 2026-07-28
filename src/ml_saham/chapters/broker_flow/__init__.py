"""Ch.6 Broker & foreign flow — Sub-Ensemble Audit for Flow."""

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

META = get_meta("broker-flow")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah pembobotan sub-komponen flow (cons, streak, vwap, dll) ",
        "  adalah racikan terbaik, atau justru suboptimal secara empiris?",
        "",
        "Pendekatan",
        "  • Baseline: Skor akhir menggunakan configured_weight statis ai-saham.",
        "  • SOTA: Skor dioptimasi ulang oleh Ridge Regression secara dinamis.",
        "",
        f"Lanjut:  ml-saham challenge engine --category signal --scenario accum --type flow",
    ]
    if verbose:
        lines.append("\nDetail: Evaluasi Sub-Ensemble Flow Engine.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    raise NotImplementedError("Gunakan mode challenge (run_compare) untuk evaluasi Flow Engine.")


def run_compare(ctx: ChapterContext, **kwargs) -> DemoResult:
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
    
    # Komponen dari flow_signals
    feature_names = ["cons", "streak", "vwap", "flow", "inst"]
    ai_saham_weights = {}

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            
            signal = payload.get("signal", {})
            flow_ev = signal.get("flow_evidence")
            if not flow_ev:
                continue
                
            signals = flow_ev.get("flow_signals", [])
            if not signals:
                continue
            
            # Kumpulkan skor mentah per pilar flow
            feats = []
            for fname in feature_names:
                score = 0.0
                for s in signals:
                    if s.get("key") == fname:
                        score = float(s.get("score", 0.0))
                        if fname not in ai_saham_weights:
                            ai_saham_weights[fname] = float(s.get("weight", 0.0))
                        break
                feats.append(score)
            
            # Baseline score = kombinasi asli ai-saham (ex_bb score atau uncapped_strength)
            # Kita gunakan flow_score_ex_bb jika ada
            flow_score = float(flow_ev.get("flow_score_ex_bb", flow_ev.get("uncapped_strength", 0.0)))
            
            # Ekstrak Target Y (forward return 5 session / proksi)
            fingerprint = payload.get("sub_signal_fingerprint", {})
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                fwd_ret = float(excess_5d["excess_return_pct"])
            else:
                fwd_ret = flow_score / 100.0  # mock proxy if no return

            X_list.append(feats)
            y_list.append(fwd_ret)
            baseline_scores.append(flow_score)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
            
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing JSON payload flow_signals.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    # Baseline Rank IC
    baseline_ic = rank_ic(baseline_scores, y_arr.tolist())

    # 3. Train SOTA (Ridge Regression)
    try:
        from sklearn.linear_model import Ridge
        clf = Ridge(alpha=10.0, random_state=42)
        
        if len(set(y_arr)) > 1:
            clf.fit(X_arr, y_arr)
            sota_scores = clf.predict(X_arr)
            sota_ic = rank_ic(sota_scores.tolist(), y_arr.tolist())
            
            importances = np.abs(clf.coef_)
            if importances.sum() > 0:
                importances = (importances / importances.sum()) * 100
            imp_source = "Ridge Coef"
        else:
            sota_ic = 0.0
            importances = np.zeros(len(feature_names))
            imp_source = "None"
            
    except ImportError:
        sota_ic = 0.0
        importances = np.zeros(len(feature_names))
        imp_source = "None"

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}  purpose={purpose}",
        "Perbandingan Flow Sub-Ensemble SOTA (Ridge) vs Baseline (AI-Saham Weights)",
        "",
        f"Baseline Rank IC : {baseline_ic:+.3f}",
        f"SOTA Rank IC     : {sota_ic:+.3f}",
        "",
        f"=== Analisis Rekomendasi Bobot Sejati ({imp_source}) vs (AI-Saham) ==="
    ]
    
    md_lines = [
        f"# Flow Sub-Ensemble Compare ({purpose})\n",
        "SOTA ML Dynamic Weights vs Baseline Static Weights.\n",
        f"- **Baseline Rank IC:** {baseline_ic:+.3f}",
        f"- **SOTA Rank IC:** {sota_ic:+.3f}\n",
        f"### Analisis Rekomendasi Bobot Flow ({imp_source}) vs (ai-saham)",
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
        "sota_ic": float(sota_ic),
    }

    return DemoResult(
        title="Flow Sub-Ensemble · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="ridge_flow_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )

def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="signal engine / flow",
        bring_back="Flow vs ML",
    )
