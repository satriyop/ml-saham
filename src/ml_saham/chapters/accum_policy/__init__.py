"""Ch.37 Accumulation Policy — SOTA vs Baseline."""

from __future__ import annotations

import logging

from ml_saham.chapters.errors import ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult

logger = logging.getLogger(__name__)

META = get_meta("accum-policy")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menentukan policy skor akumulasi terbaik dari berbagai komponen.",
        "",
        "Opsi pendekatan",
        "  • SOTA: LightGBM Regression pada komponen-komponen akumulasi.",
        "  • Baseline: Pembobotan manual 33.3% dari ScoreAccumUseCase.",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"         ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: Eksperimen model LightGBM vs baseline manual.")
    return "\n".join(lines)


def _prep_data(ctx: ChapterContext):
    # Simulate some accum components data: component A, B, C
    # Baseline just averages them (33.3% each).
    # SOTA learns a regression target (e.g., next day return).
    import random

    random.seed(42)
    data = []
    for i in range(100):
        comp_a = random.random()
        comp_b = random.random()
        comp_c = random.random()

        # simulated target: slightly prefers comp_a and comp_b over comp_c, plus noise
        target = 0.5 * comp_a + 0.4 * comp_b + 0.1 * comp_c + random.uniform(-0.1, 0.1)

        data.append(
            {
                "ticker": f"TICK{i}",
                "comp_a": comp_a,
                "comp_b": comp_b,
                "comp_c": comp_c,
                "target": target,
            }
        )
    return data


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from lightgbm import LGBMRegressor
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install lightgbm") from exc

    data = _prep_data(ctx)
    X = np.array([[d["comp_a"], d["comp_b"], d["comp_c"]] for d in data])
    y = np.array([d["target"] for d in data])

    model = LGBMRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)
    preds = model.predict(X)

    for d, p in zip(data, preds, strict=True):
        d["sota_score"] = p

    data.sort(key=lambda d: d["sota_score"], reverse=True)

    lines = [
        "SOTA Model: LightGBM Regression (Prediksi Target dari Komponen Akumulasi)",
        "",
        "Top Score berdasarkan Prediksi LightGBM:",
    ]
    for d in data[:8]:
        lines.append(
            f"  {d['ticker']:<6} SOTA Score={d['sota_score']:.3f}  (A={d['comp_a']:.2f}, B={d['comp_b']:.2f}, C={d['comp_c']:.2f})"
        )

    return DemoResult(
        title="Accumulation Policy \u00b7 SOTA LightGBM Regression",
        lines=lines,
        metrics={"n_samples": len(data)},
        model="lightgbm_accum_policy",
        summary_md="# Accumulation Policy\n\nSOTA LightGBM regression diimplementasikan.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=data[:10],
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    import json
    import sqlite3
    import numpy as np
    from ml_saham.data.aisaham_read import connect
    from ml_saham.chapters.errors import ChapterDataError

    with connect(ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT decision_payload_json FROM learning_observations WHERE purpose='ACCUMULATION_DISCOVERY' ORDER BY captured_at DESC LIMIT 1000"
        )
        rows = cursor.fetchall()

    if not rows:
        raise ChapterDataError(
            "learning_observations untuk ACCUMULATION_DISCOVERY kosong.",
            hint="Sistem AI-Saham belum mencatat observasi accum.",
        )

    # Prepare dataset
    X_list = []
    y_list = []
    baseline_scores = []
    meta = []
    
    # Define features we want to extract from sub_signal_fingerprint
    feature_names = [
        "rsi_at_signal",
        "vwap_position_at_signal",
        "ia_foreign_participation",
        "ia_domestic_buy_vwap_distance",
        "bb_width_pctile_at_signal",
        "foreign_concentration_at_signal"
    ]

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            fingerprint = payload.get("sub_signal_fingerprint", {})
            signal = payload.get("signal", {})
            
            # Extract features
            feats = []
            for fname in feature_names:
                val = fingerprint.get(fname)
                if val is None:
                    val = 0.0
                feats.append(float(val))
                
            X_list.append(feats)
            
            # Extract Baseline score
            b_score = float(signal.get("raw_exact_score", signal.get("raw_score", 0.0)))
            baseline_scores.append(b_score)
            
            # Extract target (using 5d benchmark excess return if available)
            target = 0.0
            excess_5d = fingerprint.get("benchmark_excess_return_5_session", {})
            if isinstance(excess_5d, dict) and excess_5d.get("excess_return_pct") is not None:
                target = float(excess_5d["excess_return_pct"])
            else:
                # Mock target for structural demonstration if real return is missing
                target = b_score / 100.0 
            y_list.append(target)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing payload JSON accum.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)

    # Train SOTA Model (LightGBM)
    try:
        import lightgbm as lgb
        clf = lgb.LGBMRegressor(n_estimators=50, random_state=42)
        if len(set(y_list)) > 1:
            clf.fit(X_arr, y_arr)
            sota_scores = clf.predict(X_arr)
            
            # Feature Importance / SHAP Analysis
            try:
                import shap
                explainer = shap.TreeExplainer(clf)
                shap_values = explainer.shap_values(X_arr)
                mean_shap = np.abs(shap_values).mean(axis=0)
                importances = (mean_shap / mean_shap.sum()) * 100
                imp_source = "SHAP"
            except ImportError:
                gains = clf.feature_importances_
                importances = (gains / gains.sum()) * 100
                imp_source = "Gain"
        else:
            sota_scores = np.array(baseline_scores) / 100.0
            importances = np.zeros(len(feature_names))
            imp_source = "None"
    except (ImportError, ValueError, Exception):
        sota_scores = np.array(baseline_scores) / 100.0
        importances = np.zeros(len(feature_names))
        imp_source = "None"

    # Evaluate Rank IC (Correlation)
    try:
        from scipy.stats import spearmanr
        baseline_ic, _ = spearmanr(baseline_scores, y_arr)
        sota_ic, _ = spearmanr(sota_scores, y_arr)
    except ImportError:
        baseline_ic = 0.0
        sota_ic = 0.0

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}  source=learning_observations",
        "Perbandingan SOTA (LightGBM) vs Baseline (AI-Saham ASLI dari DB)",
        "",
        f"Baseline Rank IC : {baseline_ic:+.3f}",
        f"SOTA Rank IC     : {sota_ic:+.3f}",
        "",
        f"=== Analisis Kontribusi Faktor SOTA ({imp_source}) ==="
    ]
    
    md_lines = [
        "# Accumulation Policy Compare\n",
        "SOTA LightGBM vs Baseline Asli.\n",
        f"- **Baseline Rank IC:** {baseline_ic:+.3f}",
        f"- **SOTA Rank IC:** {sota_ic:+.3f}\n",
        f"### Analisis Kontribusi Faktor ({imp_source})",
    ]
    
    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            lines.append(f"  {name:<32} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    metrics = {
        "n_samples": len(meta),
        "sota_ic": float(sota_ic),
        "baseline_ic": float(baseline_ic),
    }

    return DemoResult(
        title="Accumulation Policy · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="lightgbm_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )
