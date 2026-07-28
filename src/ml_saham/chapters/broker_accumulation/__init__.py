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
        from sklearn.linear_model import LogisticRegression
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
                "date": br["date"],
            }
        )

    combined.sort(key=lambda c: (c["inst_pct"], c["top3_ratio"]), reverse=True)

    lines = [
        f"n_shareholding={len(s_rows)}  n_broker_dist={len(b_rows)}",
        "Concentration Metrics: Gini Index & Top-3 Broker Net Accumulation",
        "",
        "Top institutional accumulation names:",
    ]

    for c in combined[:10]:
        lines.append(
            f"  {c['ticker']:<6} Inst={c['inst_pct']:5.1f}%  "
            f"TopHolder={c['top_holder_pct']:5.1f}%  "
            f"Gini={c['gini']:.3f}  Top3BrokerAccum={c['top3_ratio']:.1%}"
        )

    metrics = {
        "n_shareholding": len(s_rows),
        "n_broker_dist": len(b_rows),
        "mean_inst_pct": float(np.mean([c["inst_pct"] for c in combined])) if combined else 0.0,
        "mean_gini": float(np.mean([c["gini"] for c in combined])) if combined else 0.0,
    }
    return DemoResult(
        title="Broker accumulation · top-N concentration & Gini",
        lines=lines,
        metrics=metrics,
        model="gini_broker_accumulation",
        summary_md=f"# Broker accumulation\n\n{len(combined)} tickers evaluated.\n",
        scoreboard=False,
        scoreboard_kind="none",
        top_names=[{"ticker": c["ticker"], "inst_pct": c["inst_pct"], "gini": c["gini"]} for c in combined[:10]],
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="broker_distribution_cache & shareholding_composition di ai-saham",
        bring_back="Gini concentration index + Top3 broker accumulation ratio habit",
    )
