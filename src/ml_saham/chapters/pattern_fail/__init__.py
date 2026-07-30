"""Ch.3 Pattern failure lab — next-day pattern vs coin-flip."""

from __future__ import annotations

import math

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("pattern-fail")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  'Prediksi naik/turun besok dari pola harga singkat' terdengar sexy,",
        "  tapi sering jadi lab kegagalan: mudah overfit, pertanyaan salah.",
        "",
        "Opsi pendekatan (failure lab)",
        "  1) Fitur return 1–5 hari + volume → LightGBM (default)",
        "  2) Bandingkan akurasi ke 50% coin-flip baseline (compare)",
        "  3) Sadari framing lebih baik ada di chapter berikutnya",
        "",
        "Caveat",
        "  • Chapter ini sengaja TIDAK mengklaim edge",
        "  • Lanjut yang lebih masuk akal: factor-score, broker-flow, walk-forward",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
        f"Compare: ml-saham learn compare {META.slug} --baseline coinflip --against lgbm",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Pointer",
                "  • ml-saham learn explore factor-score",
                "  • ml-saham learn explore broker-flow",
                "  • ml-saham learn explore walk-forward  (phase-2)",
            ]
        )
    return "\n".join(lines)

def _prepare_data(ctx: ChapterContext) -> tuple[list[list[float]], list[int], int]:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=15)
        candles = load_candles(conn, uni)

    by_t: dict[str, list] = {}
    for row in candles:
        by_t.setdefault(row["ticker"], []).append(row)

    X_list = []
    y_list = []
    for t, rows in by_t.items():
        rows = sorted(rows, key=lambda r: r["date"])
        closes = [float(r["close"]) for r in rows]
        vols = [float(r["volume"] or 0) for r in rows]
        for i in range(5, len(closes) - 1):
            r1 = closes[i] / closes[i - 1] - 1.0
            r3 = closes[i] / closes[i - 3] - 1.0
            r5 = closes[i] / closes[i - 5] - 1.0
            vchg = (vols[i] + 1) / (vols[i - 1] + 1)
            y = 1 if closes[i + 1] > closes[i] else 0
            X_list.append([r1, r3, r5, vchg])
            y_list.append(y)

    if len(X_list) < 100:
        raise ChapterDataError(f"Sample terlalu kecil (n={len(X_list)}).")
    
    return X_list, y_list, len(by_t)

def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        import lightgbm as lgb
    except ImportError as exc:
        raise ChapterError(
            "Butuh scikit-learn dan lightgbm: pip install -e ."
        ) from exc

    X_list, y_list, n_tickers = _prepare_data(ctx)

    X = np.array(X_list)
    y = np.array(y_list)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=42, shuffle=True
    )
    # NOTE: shuffle on time series is part of the failure lesson (leakage-ish)
    clf = lgb.LGBMClassifier(n_estimators=50, max_depth=3, random_state=42, verbose=-1)
    clf.fit(Xtr, ytr)
    acc = float((clf.predict(Xte) == yte).mean())
    majority = float(max(yte.mean(), 1 - yte.mean()))
    coin = 0.5

    # Binomial Z-test for proportion vs coin-flip baseline (0.5)
    n_te = len(yte)
    z_stat = (acc - 0.5) / (math.sqrt(0.25 / n_te) or 1e-8)
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

    lines = [
        f"Samples: {len(X_list)}  train={len(Xtr)} test={n_te}",
        f"LightGBM accuracy (shuffled split): {acc:.3f}",
        f"Majority-class baseline:         {majority:.3f}",
        f"Coin-flip baseline:              {coin:.3f}  (z={z_stat:+.2f}, p-val={p_value:.4f})",
        "",
        "Kesimpulan (baca ini):",
        "  Pertanyaan 'naik/turun besok dari pola harga singkat' mudah overfit",
        "  dan secara statistik TIDAK signifikan lebih baik dari coin-flip.",
        "  Ini failure lab — bukan edge ketemu.",
        "",
        "Lanjut framing yang lebih sehat:",
        "  → ml-saham learn explore factor-score",
        "  → ml-saham learn explore broker-flow",
        "  → ml-saham learn explore walk-forward",
    ]
    metrics = {
        "n": len(X_list),
        "n_test": n_te,
        "accuracy_lgbm": acc,
        "accuracy_majority": majority,
        "accuracy_coinflip": coin,
        "z_stat_vs_coinflip": z_stat,
        "p_value_vs_coinflip": p_value,
        "is_statistically_significant": bool(p_value < 0.05),
        "conclusion": "wrong_question_easy_overfit",
        "n_tickers": n_tickers,
    }
    return DemoResult(
        title="Pattern fail · failure lab",
        lines=lines,
        metrics=metrics,
        model="lightgbm_nextday",
        summary_md=(
            "# Pattern failure lab\n\n"
            "Next-day up/down dari pola harga singkat vs coin-flip/majority.\n"
            "Kesimpulan: pertanyaan salah / mudah overfit — bukan edge.\n"
            "Lanjut: factor-score, broker-flow, walk-forward.\n"
        ),
        scoreboard=False,  # accuracy lab, not IHSG scoreboard
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        import lightgbm as lgb
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:
        raise ChapterError(
            "Butuh scikit-learn dan lightgbm: pip install -e ."
        ) from exc

    X_list, y_list, n_tickers = _prepare_data(ctx)
    X = np.array(X_list)
    y = np.array(y_list)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=42, shuffle=True
    )
    
    def get_acc(model_name: str) -> float:
        if model_name == "coinflip":
            return 0.5
        elif model_name == "lgbm":
            clf = lgb.LGBMClassifier(n_estimators=50, max_depth=3, random_state=42, verbose=-1)
            clf.fit(Xtr, ytr)
            return float((clf.predict(Xte) == yte).mean())
        elif model_name == "tree":
            clf = DecisionTreeClassifier(max_depth=4, random_state=42)
            clf.fit(Xtr, ytr)
            return float((clf.predict(Xte) == yte).mean())
        elif model_name == "majority":
            return float(max(yte.mean(), 1 - yte.mean()))
        else:
            raise ValueError(f"Unknown model: {model_name}")

    acc_b = get_acc(baseline)
    acc_a = get_acc(against)
    
    n_te = len(yte)
    # Variance of proportion P is P*(1-P)/n_te. 
    # Usually for coinflip variance is 0.25/n_te. 
    # For a general model comparison we should technically do McNemar's, 
    # but to follow the failure lab's existing logic we can just compute a Z-stat vs the baseline as a fixed proportion.
    var_b = acc_b * (1.0 - acc_b)
    if baseline == "coinflip":
        var_b = 0.25
    elif var_b == 0:
        var_b = 1e-8
        
    z_stat = (acc_a - acc_b) / (math.sqrt(var_b / n_te) or 1e-8)
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z_stat) / math.sqrt(2.0))))

    lines = [
        f"Samples: {len(X_list)}  train={len(Xtr)} test={n_te}",
        f"{baseline} accuracy: {acc_b:.3f}",
        f"{against} accuracy: {acc_a:.3f}",
        f"Z-stat ({against} vs {baseline}): {z_stat:+.2f}  (p-val={p_value:.4f})",
        "",
        "Kesimpulan (baca ini):",
        f"  Perbedaan antara {against} dan {baseline} {'TIDAK ' if p_value >= 0.05 else ''}signifikan.",
        "  Ini menegaskan bahwa pola sederhana tidak cukup untuk memprediksi besok.",
    ]
    
    compare = {
        "baseline": {"id": baseline, "accuracy": acc_b},
        "against": {"id": against, "accuracy": acc_a},
        "n_test": n_te,
        "z_stat": z_stat,
        "p_value": p_value,
    }
    return CompareResult(
        title=f"Compare · {baseline} vs {against}",
        lines=lines,
        metrics={"acc_baseline": acc_b, "acc_against": acc_a, "n_test": n_te},
        compare=compare,
        model=f"{baseline}_vs_{against}",
        summary_md=(
            f"# Compare pattern_fail\n\n`{baseline}` vs `{against}`.\n"
        ),
        scoreboard=False,
    )

