"""Ch.3 Pattern failure lab — next-day pattern vs coin-flip."""

from __future__ import annotations

from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
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
        "  1) Fitur return 1–5 hari + volume → tree / k-NN",
        "  2) Bandingkan akurasi ke coin-flip / majority class",
        "  3) Sadari framing lebih baik ada di chapter berikutnya",
        "",
        "Caveat",
        "  • Chapter ini sengaja TIDAK mengklaim edge",
        "  • Lanjut yang lebih masuk akal: factor-score, broker-flow, walk-forward",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Pointer",
                "  • ml-saham explore factor-score",
                "  • ml-saham explore broker-flow",
                "  • ml-saham explore walk-forward  (phase-2)",
            ]
        )
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:
        raise RuntimeError(
            "Butuh scikit-learn: pip install scikit-learn / 'ml-saham[ml]'"
        ) from exc

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
        raise RuntimeError(f"Sample terlalu kecil (n={len(X_list)}).")

    X = np.array(X_list)
    y = np.array(y_list)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=42, shuffle=True
    )
    # NOTE: shuffle on time series is part of the failure lesson (leakage-ish)
    clf = DecisionTreeClassifier(max_depth=4, random_state=42)
    clf.fit(Xtr, ytr)
    acc = float((clf.predict(Xte) == yte).mean())
    majority = float(max(yte.mean(), 1 - yte.mean()))
    coin = 0.5

    lines = [
        f"Samples: {len(X_list)}  train={len(Xtr)} test={len(Xte)}",
        f"Tree accuracy (shuffled split): {acc:.3f}",
        f"Majority-class baseline:         {majority:.3f}",
        f"Coin-flip baseline:              {coin:.3f}",
        "",
        "Kesimpulan (baca ini):",
        "  Pertanyaan 'naik/turun besok dari pola harga singkat' mudah overfit",
        "  dan sering TIDAK lebih baik dari baseline bodoh secara bermakna.",
        "  Ini failure lab — bukan edge ketemu.",
        "",
        "Lanjut framing yang lebih sehat:",
        "  → ml-saham explore factor-score",
        "  → ml-saham explore broker-flow",
        "  → ml-saham explore walk-forward",
    ]
    metrics = {
        "n": len(X_list),
        "accuracy_tree": acc,
        "accuracy_majority": majority,
        "accuracy_coinflip": coin,
        "conclusion": "wrong_question_easy_overfit",
        "n_tickers": len(by_t),
    }
    return DemoResult(
        title="Pattern fail · failure lab",
        lines=lines,
        metrics=metrics,
        model="decision_tree_nextday",
        summary_md=(
            "# Pattern failure lab\n\n"
            "Next-day up/down dari pola harga singkat vs coin-flip/majority.\n"
            "Kesimpulan: pertanyaan salah / mudah overfit — bukan edge.\n"
            "Lanjut: factor-score, broker-flow, walk-forward.\n"
        ),
        scoreboard=False,  # accuracy lab, not IHSG scoreboard
    )
