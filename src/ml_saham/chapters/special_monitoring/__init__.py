"""Ch.30 Special monitoring — exchange notation, UMA & liquidity risk classifier."""

from __future__ import annotations

from collections import defaultdict
import json

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_ticker_notations
from ml_saham.eval.metrics import rank_ic

META = get_meta("special-monitoring")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mengidentifikasi saham berisiko tinggi terkena notasi khusus bursa (Papan Pemantauan Khusus),",
        "  peringatan UMA (Unusual Market Activity), dan potongan Haircut Margin 100%.",
        "",
        "Opsi pendekatan",
        "  1) Vektor Sinyal Risiko Bursa (has_uma, haircut_pct, corp_action_active, tradeable)",
        "  2) Decision Tree / Logistic Risk Classifier Prediksi Downside Tail Risk",
        "  3) Skor Risiko Likuiditas & Filter Notasi Bursa",
        "",
        "Caveat",
        "  • Notasi khusus bursa diterbitkan secara berkala oleh BEI/IDX",
        "  • Saham UMA kadang mengalami lonjakan spekulatif sangat tinggi sebelum suspensi",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: ticker_notation_cache di ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")

        notation_rows = load_ticker_notations(conn, uni)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    if not notation_rows:
        raise ChapterDataError(
            "ticker_notation_cache kosong.",
            hint="ml-saham doctor",
        )

    by_t = {r["ticker"]: r for r in notation_rows if r["ticker"] in fwd}
    tickers = sorted(by_t.keys())

    if len(tickers) < 8:
        raise ChapterDataError(f"Panel ticker_notation_cache terlalu kecil (n={len(tickers)}).")

    X_list, y_list = [], []
    risk_scores: dict[str, float] = {}

    for t in tickers:
        r = by_t[t]
        has_uma = 1.0 if int(r.get("has_uma") or 0) == 1 else 0.0
        tradeable = 1.0 if int(r.get("tradeable") or 1) == 1 else 0.0
        corp_active = 1.0 if int(r.get("corp_action_active") or 0) == 1 else 0.0

        raw_haircut = str(r.get("haircut_percentage") or "0").replace("%", "").strip()
        try:
            haircut_pct = float(raw_haircut)
        except ValueError:
            haircut_pct = 50.0

        # Higher risk score = safer stock (100 - haircut + tradeable - UMA)
        safety_score = (100.0 - haircut_pct) + (tradeable * 20.0) - (has_uma * 40.0)
        risk_scores[t] = safety_score

        fwd_ret = float(fwd[t])
        label = 1 if fwd_ret >= -0.02 else 0  # Severe downside tail risk protection label

        X_list.append([has_uma, tradeable, corp_active, haircut_pct])
        y_list.append(label)

    scores = [risk_scores[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)

    X_arr, y_arr = np.array(X_list), np.array(y_list)
    dt = DecisionTreeClassifier(max_depth=3, random_state=42)
    dt.fit(X_arr, y_arr)
    acc = float(dt.score(X_arr, y_arr))

    uma_count = sum(1 for t in tickers if int(by_t[t].get("has_uma") or 0) == 1)
    high_haircut_count = sum(1 for t in tickers if "100" in str(by_t[t].get("haircut_percentage") or ""))

    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {"ticker": tickers[i], "safety_score": scores[i], "fwd": rets[i]}
        for i in order[:10]
    ]

    lines = [
        f"as_of={as_of}  n_tickers={len(tickers)}  source=ticker_notation_cache",
        f"Exchange Risk Safety Score Rank IC:      {ic:+.3f}",
        f"Decision Tree Tail-Risk In-Sample Acc:   {acc:.1%}",
        f"Exchange Flags Breakdown: UMA={uma_count}  100%Haircut={high_haircut_count}",
        "",
        "Top Clean & High Safety Rated Stocks (Lowest Exchange Risk):",
    ]

    for t in top[:8]:
        uma_flag = "UMA" if int(by_t[t['ticker']].get("has_uma") or 0) == 1 else "Clean"
        lines.append(
            f"  {t['ticker']:<6} SafetyScore={t['safety_score']:5.1f}  Status={uma_flag:<5}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n_tickers": len(tickers),
        "rank_ic_safety_score": ic,
        "model_accuracy": acc,
        "uma_count": uma_count,
        "high_haircut_count": high_haircut_count,
    }
    return DemoResult(
        title="Special monitoring · exchange risk classifier",
        lines=lines,
        metrics=metrics,
        model="dt_special_monitoring",
        summary_md=f"# Special monitoring\n\nRank IC={ic:+.3f}. Accuracy={acc:.1%}.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="ticker_notation_cache di ai-saham",
        bring_back="exchange UMA notation + margin haircut risk habit",
    )
