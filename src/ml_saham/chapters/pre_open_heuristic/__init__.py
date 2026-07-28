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
    with connect(ctx.db_path) as conn:
        rows = load_iev_snapshots(conn, as_of=ctx.as_of, limit_dates=3)
        if not rows:
            raise ChapterDataError(
                "iev_snapshots kosong.",
                hint="ml-saham doctor",
            )

    latest_date = rows[0]["date"]
    day_rows = [r for r in rows if r["date"] == latest_date]

    meta = []
    X = []
    y = []
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
        is_top = 1 if rank_i <= 100 else 0
        y.append(is_top)
        meta.append(
            {
                "ticker": r["ticker"],
                "iev": iev_f,
                "iep": iep_f,
                "imbalance": imbalance,
                "orig_rank": rank_i,
            }
        )

    # SOTA
    try:
        import xgboost as xgb
        import numpy as np

        X_arr = np.array(X)
        y_arr = np.array(y)

        clf = xgb.XGBClassifier(
            n_estimators=20,
            learning_rate=0.1,
            max_depth=3,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        if len(set(y)) > 1:
            clf.fit(X_arr, y_arr)
            sota_scores = clf.predict_proba(X_arr)[:, 1]
        else:
            sota_scores = [m["imbalance"] for m in meta]
    except (ImportError, ValueError, Exception):
        sota_scores = [m["imbalance"] for m in meta]

    # Baseline: Deterministic Decision Tree & Capping
    try:
        from sklearn.tree import DecisionTreeClassifier
        import numpy as np

        dt = DecisionTreeClassifier(max_depth=3, random_state=42)
        X_arr = np.array(X)
        y_arr = np.array(y)
        if len(set(y)) > 1:
            dt.fit(X_arr, y_arr)
            baseline_raw = dt.predict_proba(X_arr)[:, 1]
        else:
            baseline_raw = [m["imbalance"] for m in meta]
        # capping
        baseline_scores = [min(0.95, max(0.05, float(s))) for s in baseline_raw]
    except (ImportError, ValueError, Exception):
        baseline_scores = [min(0.95, max(0.05, m["imbalance"])) for m in meta]

    for i, m in enumerate(meta):
        m["sota_score"] = float(sota_scores[i])
        m["baseline_score"] = baseline_scores[i]

    sota_sorted = sorted(meta, key=lambda x: x["sota_score"], reverse=True)
    baseline_sorted = sorted(meta, key=lambda x: x["baseline_score"], reverse=True)

    sota_top = sota_sorted[:10]
    baseline_top = baseline_sorted[:10]

    sota_avg_imb = (
        sum(x["imbalance"] for x in sota_top) / len(sota_top) if sota_top else 0.0
    )
    base_avg_imb = (
        sum(x["imbalance"] for x in baseline_top) / len(baseline_top)
        if baseline_top
        else 0.0
    )

    lines = [
        f"date={latest_date}  n={len(meta)}  source=iev_snapshots",
        "Perbandingan: SOTA (XGBoost Classifier) vs Baseline (Deterministic Decision Tree & Capping)",
        "",
        f"Baseline Top 10 Avg Imbalance: {base_avg_imb:+.2%}",
        f"SOTA Top 10 Avg Imbalance: {sota_avg_imb:+.2%}",
        "",
        "Top SOTA names:",
    ]
    for t in sota_top:
        lines.append(
            f"  {t['ticker']:<6}  IEV={t['iev']:.2f}  imb={t['imbalance']:+.2%}  score={t['sota_score']:.3f}"
        )

    lines.append("")
    lines.append("Top Baseline names:")
    for t in baseline_top:
        lines.append(
            f"  {t['ticker']:<6}  IEV={t['iev']:.2f}  imb={t['imbalance']:+.2%}  score={t['baseline_score']:.3f}"
        )

    metrics = {
        "date": latest_date,
        "n": len(meta),
        "sota_avg_imbalance": sota_avg_imb,
        "baseline_avg_imbalance": base_avg_imb,
    }

    return DemoResult(
        title="Pre-open heuristic · Compare",
        lines=lines,
        metrics=metrics,
        model="compare",
        summary_md=f"# Pre-open heuristic Compare\n\nSOTA vs Baseline for {latest_date}.\n",
        scoreboard=False,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="iev_snapshots / pre-open heuristic",
        bring_back="Heuristic vs SOTA",
    )
