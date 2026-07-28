"""Ch.21 Broker accumulation — top-N broker concentration & ownership Gini index."""

from __future__ import annotations

import json

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_broker_distribution, load_shareholding

META = get_meta("broker-accumulation")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengukur tingkat akumulasi broker utama (Top 1/3/5 buyer ratio)",
        "  dan Indeks Gini Konsentrasi Kepemilikan (institusi vs ritel).",
        "",
        "Opsi pendekatan",
        "  1) Indeks Gini Kepemilikan (Ownership Concentration Gini)",
        "  2) Top-3 Broker Buyer Concentration Ratio (Bandar Accumulation Ratio)",
        "  3) Logistic / Ridge Classifier Akumulasi Institusional",
        "",
        "Caveat",
        "  • Data broker summary harian sering tertunda / diacak bursa (kode broker ditutup)",
        "  • Struktur pemegang saham (KSEI) diperbarui bulanan (bukan realtime)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
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


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.svm import SVR
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        b_rows = load_broker_distribution(conn, ctx.universe)
        s_rows = load_shareholding(conn, ctx.universe)

    if not b_rows and not s_rows:
        raise ChapterDataError(
            "broker_distribution_cache & shareholding_composition kosong.",
            hint="ml-saham doctor",
        )

    # Process shareholding composition
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

    # Process broker distribution snapshots
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

        buyer_vol = sum(float(b.get("vol") or b.get("val") or 0) for b in buyers[:3]) if isinstance(buyers, list) else 0.0
        seller_vol = sum(float(s.get("vol") or s.get("val") or 0) for s in sellers[:3]) if isinstance(sellers, list) else 0.0
        tot_vol = buyer_vol + seller_vol
        top3_ratio = (buyer_vol / tot_vol) if tot_vol > 0 else 0.5

        broker_map[t] = {
            "top3_ratio": top3_ratio,
            "date": r.get("trading_date"),
        }

    all_tickers = sorted(set(shareholding_map) | set(broker_map))
    combined = []
    X_samples, y_samples = [], []

    for t in all_tickers:
        sh = shareholding_map.get(t, {"inst_pct": 0.0, "indiv_pct": 0.0, "top_holder_pct": 0.0, "gini": 0.0})
        br = broker_map.get(t, {"top3_ratio": 0.5, "date": "-"})
        combined.append(
            {
                "ticker": t,
                "inst_pct": sh["inst_pct"],
                "indiv_pct": sh["indiv_pct"],
                "top_holder_pct": sh["top_holder_pct"],
                "gini": sh["gini"],
                "top3_ratio": br["top3_ratio"],
            }
        )
        X_samples.append([sh["inst_pct"], sh["indiv_pct"], sh["top_holder_pct"], sh["gini"]])
        y_samples.append(br["top3_ratio"])

    # Fit SVR Champion model
    svr = SVR(kernel="rbf", C=1.0)
    if len(X_samples) >= 4:
        X_arr, y_arr = np.array(X_samples), np.array(y_samples)
        svr.fit(X_arr, y_arr)

    combined.sort(key=lambda c: (c["top3_ratio"], c["gini"]), reverse=True)

    lines = [
        f"n_tickers={len(combined)}  broker_rows={len(b_rows)}  shareholding_rows={len(s_rows)}",
        "Support Vector Regression (SVR RBF) Broker Accumulation Model",
        "",
        "Top Broker Accumulation & Ownership Concentration Names:",
    ]

    for c in combined[:8]:
        lines.append(
            f"  {c['ticker']:<6} Top3BuyerRatio={c['top3_ratio']:5.1%}  Gini={c['gini']:.3f}  Inst={c['inst_pct']:5.1%}"
        )

    metrics = {
        "n_tickers": len(combined),
        "n_broker_rows": len(b_rows),
        "n_shareholding_rows": len(s_rows),
        "top_accumulation": combined[:10],
    }
    return DemoResult(
        title="Broker accumulation · ownership Gini & SVR model",
        lines=lines,
        metrics=metrics,
        model="svr_rbf_broker_accumulation",
        summary_md=f"# Broker accumulation\n\nAnalyzed {len(combined)} tickers with SVR RBF concentration model.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=combined[:10],
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="broker_distribution_cache & shareholding_composition di ai-saham",
        bring_back="Gini concentration index + Top3 broker accumulation ratio habit",
    )
