"""Ch.23 Broker accumulation — top-N broker concentration & ownership Gini index."""

from __future__ import annotations

import json
import logging

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_broker_distribution, load_shareholding

logger = logging.getLogger(__name__)

META = get_meta("broker-accumulation")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur tingkat akumulasi broker utama (Top-N buyer ratio)",
        "  dan Indeks Gini Konsentrasi Kepemilikan (institusi vs ritel).",
        "",
        "Opsi pendekatan",
        "  • default (Default): LightGBM classification (memprediksi probabilitas akumulasi dari fitur distribusi broker & kepemilikan)",
        "  • Baseline (Compare): Top-5 broker sum rule (rasio konsentrasi top-5 broker vs total)",
        "",
        "Caveat",
        "  • Data broker summary harian sering tertunda / diacak bursa (kode broker ditutup)",
        "  • Struktur pemegang saham (KSEI) diperbarui bulanan (bukan realtime)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
        f"         ml-saham learn compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_broker_distribution & load_shareholding di ai-saham.")
    return "\n".join(lines)

def _gini_coefficient(values: list[float]) -> float:
    """Calculate Gini coefficient of a list of non-negative values."""
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    index = range(1, n + 1)
    return (2.0 * sum(i * v for i, v in zip(index, sorted_vals, strict=True)) - (n + 1) * sum(sorted_vals)) / (n * sum(sorted_vals))

def _prep_data(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        b_rows = load_broker_distribution(conn, ctx.universe)
        s_rows = load_shareholding(conn, ctx.universe)

    if not b_rows and not s_rows:
        raise ChapterDataError(
            "broker_distribution_cache & shareholding_composition kosong.",
            hint="ml-saham doctor",
        )

    shareholding_map = {}
    for r in s_rows:
        t = r["ticker"]
        inst_pct = float(r.get("institution_pct") or 0.0)
        indiv_pct = float(r.get("individual_pct") or 0.0)
        top_holder_pct = float(r.get("top_holder_pct") or 0.0)
        gini = _gini_coefficient([inst_pct, indiv_pct, top_holder_pct])
        shareholding_map[t] = {
            "inst_pct": inst_pct,
            "indiv_pct": indiv_pct,
            "top_holder_pct": top_holder_pct,
            "gini": gini,
        }

    broker_map = {}
    for r in b_rows:
        t = r["ticker"]
        if t in broker_map:
            continue
        top_buyers_str = r.get("top_buyers_json") or "[]"
        top_sellers_str = r.get("top_sellers_json") or "[]"

        try:
            buyers = json.loads(top_buyers_str)
            sellers = json.loads(top_sellers_str)
        except Exception:
            buyers, sellers = [], []

        buyer_vol_top5 = sum(float(b.get("vol") or b.get("val") or 0) for b in buyers[:5]) if isinstance(buyers, list) else 0.0
        seller_vol_top5 = sum(float(s.get("vol") or s.get("val") or 0) for s in sellers[:5]) if isinstance(sellers, list) else 0.0
        
        tot_vol_top5 = buyer_vol_top5 + seller_vol_top5
        top5_ratio = (buyer_vol_top5 / tot_vol_top5) if tot_vol_top5 > 0 else 0.5

        # Create mock target for accumulation (label=1 if top-5 buyer dominant and gini > 0.3)
        target = 1 if (top5_ratio > 0.55 and shareholding_map.get(t, {}).get("gini", 0) > 0.3) else 0
        
        broker_map[t] = {
            "top5_ratio": top5_ratio,
            "target": target,
        }

    all_tickers = sorted(set(shareholding_map) | set(broker_map))
    combined = []
    
    for t in all_tickers:
        sh = shareholding_map.get(t, {"inst_pct": 0.0, "indiv_pct": 0.0, "top_holder_pct": 0.0, "gini": 0.0})
        br = broker_map.get(t, {"top5_ratio": 0.5, "target": 0})
        combined.append({
            "ticker": t,
            "inst_pct": sh["inst_pct"],
            "indiv_pct": sh["indiv_pct"],
            "top_holder_pct": sh["top_holder_pct"],
            "gini": sh["gini"],
            "top5_ratio": br["top5_ratio"],
            "target": br["target"]
        })
    return combined, b_rows, s_rows

def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm: pip install lightgbm") from exc

    combined, b_rows, s_rows = _prep_data(ctx)

    X_samples = [[c["inst_pct"], c["indiv_pct"], c["top_holder_pct"], c["gini"], c["top5_ratio"]] for c in combined]
    y_samples = [c["target"] for c in combined]

    model = LGBMClassifier(n_estimators=50, random_state=42)
    
    X_arr, y_arr = np.array(X_samples), np.array(y_samples)
    if len(X_samples) >= 5 and len(set(y_samples)) > 1:
        model.fit(X_arr, y_arr)
        preds = model.predict_proba(X_arr)[:, 1]
    else:
        # Not enough data or only one class
        preds = np.full(len(X_samples), 0.5)

    for c, p in zip(combined, preds):
        c["accum_prob"] = p

    combined.sort(key=lambda c: c["accum_prob"], reverse=True)

    lines = [
        f"n_tickers={len(combined)}  broker_rows={len(b_rows)}  shareholding_rows={len(s_rows)}",
        "Default model: LightGBM Classification (Probabilitas Akumulasi)",
        "",
        "Top Akumulasi berdasarkan Prediksi LightGBM:",
    ]

    for c in combined[:8]:
        lines.append(
            f"  {c['ticker']:<6} Prob={c['accum_prob']:5.1%}  Top5Ratio={c['top5_ratio']:5.1%}  Gini={c['gini']:.3f}"
        )

    metrics = {
        "n_tickers": len(combined),
        "n_broker_rows": len(b_rows),
        "n_shareholding_rows": len(s_rows),
        "top_accumulation": combined[:10],
    }
    return DemoResult(
        title="Broker accumulation · Default LightGBM Classification",
        lines=lines,
        metrics=metrics,
        model="lightgbm_broker_accumulation",
        summary_md=f"# Broker accumulation\n\nAnalyzed {len(combined)} tickers using Default LightGBM classifier.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=combined[:10],
    )

def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from lightgbm import LGBMClassifier
        from sklearn.metrics import accuracy_score
    except ImportError as exc:
        raise ChapterError("Butuh lightgbm & sklearn: pip install lightgbm scikit-learn") from exc

    combined, b_rows, s_rows = _prep_data(ctx)

    X_samples = [[c["inst_pct"], c["indiv_pct"], c["top_holder_pct"], c["gini"], c["top5_ratio"]] for c in combined]
    y_samples = [c["target"] for c in combined]

    # Baseline: Top-5 broker sum rule prediction
    # Predict 1 if top5_ratio > 0.55 else 0
    baseline_preds = [1 if c["top5_ratio"] > 0.55 else 0 for c in combined]

    # Default: LightGBM
    lgb = LGBMClassifier(n_estimators=50, random_state=42)
    X_arr, y_arr = np.array(X_samples), np.array(y_samples)
    
    if len(X_samples) >= 5 and len(set(y_samples)) > 1:
        lgb.fit(X_arr, y_arr)
        against_preds = lgb.predict(X_arr)
        
        baseline_acc = accuracy_score(y_arr, baseline_preds)
        against_acc = accuracy_score(y_arr, against_preds)
    else:
        baseline_acc = 0.0
        against_acc = 0.0

    lines = [
        "Perbandingan Model Akumulasi Broker:",
        "  • Default: LightGBM Classification",
        "  • Baseline: Top-5 Broker Sum Rule",
        "",
        f"Jumlah Sampel Ticker: {len(combined)}",
        f"Akurasi Baseline: {baseline_acc:.1%}",
        f"Akurasi default (LightGBM): {against_acc:.1%}",
        "",
        "Keterangan: LightGBM dapat menangkap interaksi antara Gini kepemilikan dan rasio broker."
    ]

    metrics = {
        "baseline_accuracy": baseline_acc,
        "against_accuracy": against_acc,
        "n_samples": len(combined),
    }

    return DemoResult(
        title="Compare Default vs Baseline: Broker Accumulation",
        lines=lines,
        metrics=metrics,
        model="lightgbm_vs_rule",
        summary_md="# Perbandingan Model\n\nBaseline menggunakan Top-5 broker sum rule vs LightGBM classification.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=combined[:10],
    )

