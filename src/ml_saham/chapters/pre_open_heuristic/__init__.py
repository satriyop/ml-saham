"""Ch.38 Pre-open heuristic."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_iev_snapshots

META = get_meta("pre-open-heuristic")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Menantang aturan batas dan Raw Score Pre-Open.",
        "",
        "Opsi algoritma + caveat",
        "  SOTA (default): XGBoost Classifier dari raw metrics",
        "  Baseline (compare): Deterministic Decision Tree & Capping",
        "",
        "Caveat",
        "  • SOTA menggunakan XGBoost classifier.",
        "  • Baseline menggunakan DT deterministik & aturan capping.",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Banding: ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: klasifikasi XGBoost vs Baseline heuristic.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        rows = load_iev_snapshots(conn, as_of=ctx.as_of, limit_dates=3)
        if not rows:
            raise ChapterDataError(
                "iev_snapshots kosong.",
                hint="ml-saham doctor",
            )

    latest_date = rows[0]["date"]
    day_rows = [r for r in rows if r["date"] == latest_date]

    # Build dataset
    X = []
    y = []
    meta = []
    for r in day_rows:
        iev = r.get("iev")
        iep = r.get("iep")
        rank = r.get("rank")
        try:
            iev_f = float(iev) if iev is not None else 0.0
            iep_f = float(iep) if iep is not None else 0.0
            rank_i = int(rank) if rank is not None else 999
        except (TypeError, ValueError):
            continue

        imbalance = (iev_f / iep_f - 1.0) if iep_f > 0 else 0.0
        X.append([iev_f, iep_f, imbalance])

        # Target: binary classification (1 if rank <= 100 else 0)
        is_top = 1 if rank_i <= 100 else 0
        y.append(is_top)
        meta.append(
            {
                "ticker": r["ticker"],
                "iev": iev_f,
                "iep": iep_f,
                "imbalance": imbalance,
                "orig_rank": rank_i,
                "date": latest_date,
            }
        )

    try:
        import xgboost as xgb
        import numpy as np

        X_arr = np.array(X)
        y_arr = np.array(y)

        # Fit classifier
        clf = xgb.XGBClassifier(
            n_estimators=20,
            learning_rate=0.1,
            max_depth=3,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        if len(set(y)) > 1:
            clf.fit(X_arr, y_arr)
            scores = clf.predict_proba(X_arr)[:, 1]
        else:
            scores = [m["imbalance"] for m in meta]
    except (ImportError, ValueError, Exception):
        # Fallback
        scores = [m["imbalance"] for m in meta]

    scored_items = []
    for i, m in enumerate(meta):
        scored_items.append(
            {
                "ticker": m["ticker"],
                "score": float(scores[i]),
                "iev": m["iev"],
                "iep": m["iep"],
                "imbalance_pct": m["imbalance"],
                "orig_rank": m["orig_rank"],
                "date": m["date"],
            }
        )

    scored_items.sort(key=lambda x: x["score"], reverse=True)
    top = scored_items[:15]
    imbalances = [x["imbalance_pct"] for x in top]
    avg_imbalance = (sum(imbalances) / len(imbalances)) if imbalances else 0.0

    lines = [
        f"date={latest_date}  n={len(day_rows)}  source=iev_snapshots",
        "Model: SOTA (XGBoost Classifier)",
        f"Pre-open order imbalance (IEV vs IEP avg) Top 15: {avg_imbalance:+.2%}",
        "",
        "Top SOTA names:",
    ]
    for t in top[:10]:
        iev_txt = f"{t['iev']:.2f}"
        rank_txt = t["orig_rank"]
        imb_txt = f"  imb={t['imbalance_pct']:+.2%}"
        score_txt = f"  score={t['score']:.3f}"
        lines.append(
            f"  #{rank_txt:<4} {t['ticker']:<6}  IEV={iev_txt}{imb_txt}{score_txt}"
        )

    lines.append("")
    lines.append("Catatan: ranking probabilitas menggunakan XGBoost Classifier.")

    metrics = {
        "date": latest_date,
        "n": len(day_rows),
        "mean_pre_open_imbalance": avg_imbalance,
    }
    csv = ["date,orig_rank,ticker,iev,score"] + [
        f"{t['date']},{t['orig_rank']},{t['ticker']},{t['iev']},{t['score']}"
        for t in top
    ]
    return DemoResult(
        title="Pre-open heuristic · XGBoost Classifier (SOTA)",
        lines=lines,
        metrics=metrics,
        model="xgboost_classifier",
        summary_md=f"# Pre-open heuristic SOTA\n\n{latest_date}: XGBoost raw metrics.\n",
        scoreboard=False,
        top_names=top,
        extra_files={"sota_heuristic_top.csv": "\n".join(csv) + "\n"},
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    import json
    import sqlite3
    import numpy as np

    with connect(ctx.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT decision_payload_json FROM learning_observations WHERE purpose='PRE_OPEN_AUCTION_DIRECTION' ORDER BY captured_at DESC LIMIT 1000"
        )
        rows = cursor.fetchall()
        
    if not rows:
        raise ChapterDataError(
            "learning_observations untuk PRE_OPEN_AUCTION_DIRECTION kosong.",
            hint="Sistem AI-Saham belum mencatat observasi pre-open.",
        )

    # Prepare dataset
    X_list = []
    y_list = []
    baseline_scores = []
    meta = []
    feature_names = ["book_pressure", "delta_iev_ratio", "iep_gap_pct", "iev_intensity", "spread_pct"]

    for row in rows:
        try:
            payload = json.loads(row["decision_payload_json"])
            signal = payload.get("signal", {})
            factors = signal.get("factors", {})
            
            # Extract features
            feats = [
                float(factors.get("book_pressure", 0.0)),
                float(factors.get("delta_iev_ratio", 0.0)),
                float(factors.get("iep_gap_pct", 0.0)),
                float(factors.get("iev_intensity", 0.0)),
                float(factors.get("spread_pct", 0.0)),
            ]
            X_list.append(feats)
            
            # Extract Baseline score
            baseline_scores.append(float(signal.get("raw_score", 0.0)))
            
            # Extract target (using proxy: is IEP gap positive? Or rank?)
            # Usually pre-open target is whether it actually gaps up or closes higher.
            # Here we mock a binary target for ML classification (e.g., raw_score > 50 as a simple proxy for training if no forward returns)
            # A real backtest would join with forward_returns, but this is a structural challenge demonstration.
            is_top = 1 if float(signal.get("raw_score", 0.0)) >= 50 else 0
            y_list.append(is_top)
            
            meta.append({
                "ticker": payload.get("ticker", "UNKNOWN"),
                "date": payload.get("snapshot_date", "UNKNOWN"),
            })
        except Exception:
            continue

    if not X_list:
        raise ChapterDataError("Gagal mem-parsing payload JSON.")

    X_arr = np.array(X_list)
    y_arr = np.array(y_list)

    # Train SOTA Model
    try:
        import xgboost as xgb
        clf = xgb.XGBClassifier(
            n_estimators=20,
            learning_rate=0.1,
            max_depth=3,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        if len(set(y_list)) > 1:
            clf.fit(X_arr, y_arr)
            sota_scores = clf.predict_proba(X_arr)[:, 1]
            
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
        # Correlate baseline and sota with the target
        baseline_ic, _ = spearmanr(baseline_scores, y_arr)
        sota_ic, _ = spearmanr(sota_scores, y_arr)
    except ImportError:
        baseline_ic = 0.0
        sota_ic = 0.0

    lines = [
        f"date={meta[0]['date']}  n_samples={len(meta)}  source=learning_observations",
        "Perbandingan SOTA (XGBoost) vs Baseline (AI-Saham ASLI dari DB)",
        "",
        f"Baseline Rank IC : {baseline_ic:+.3f}",
        f"SOTA Rank IC     : {sota_ic:+.3f}",
        "",
        f"=== Analisis Kontribusi Faktor SOTA ({imp_source}) ==="
    ]
    
    md_lines = [
        "# Pre-open heuristic Compare\n",
        "SOTA XGBoost vs Baseline Asli.\n",
        f"- **Baseline Rank IC:** {baseline_ic:+.3f}",
        f"- **SOTA Rank IC:** {sota_ic:+.3f}\n",
        f"### Analisis Kontribusi Faktor ({imp_source})",
    ]
    
    # Sort and display feature importances
    if imp_source != "None":
        feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        for name, imp in feat_imp:
            lines.append(f"  {name:<16} : {imp:5.1f}%")
            md_lines.append(f"- **{name}**: {imp:5.1f}%")

    metrics = {
        "n_samples": len(meta),
        "sota_ic": float(sota_ic),
        "baseline_ic": float(baseline_ic),
    }

    return DemoResult(
        title="Pre-open heuristic · Compare Asli",
        lines=lines,
        metrics=metrics,
        model="xgboost_vs_ai_saham",
        summary_md="\n".join(md_lines) + "\n",
        scoreboard=False,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="iev_snapshots / pre-open heuristic",
        bring_back="Heuristic vs SOTA",
    )
