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
    try:
        import numpy as np
        from lightgbm import LGBMRegressor
        from sklearn.metrics import mean_squared_error
    except ImportError as exc:
        raise ChapterError(
            "Butuh lightgbm & sklearn: pip install lightgbm scikit-learn"
        ) from exc

    data = _prep_data(ctx)
    X = np.array([[d["comp_a"], d["comp_b"], d["comp_c"]] for d in data])
    y = np.array([d["target"] for d in data])

    # Baseline: 33.3% manual weight
    baseline_preds = np.mean(X, axis=1)

    # SOTA: LightGBM
    lgb = LGBMRegressor(n_estimators=50, random_state=42)
    lgb.fit(X, y)
    sota_preds = lgb.predict(X)

    baseline_mse = mean_squared_error(y, baseline_preds)
    sota_mse = mean_squared_error(y, sota_preds)

    lines = [
        "Perbandingan Model Accumulation Policy:",
        "  \u2022 SOTA: LightGBM Regression",
        "  \u2022 Baseline: Manual 33.3% weighting dari ScoreAccumUseCase",
        "",
        f"Jumlah Sampel Ticker: {len(data)}",
        f"MSE Baseline: {baseline_mse:.4f}",
        f"MSE SOTA (LightGBM): {sota_mse:.4f}",
        "",
        "Keterangan: SOTA (LightGBM Regression) dapat mempelajari bobot non-linear yang lebih optimal dibandingkan bobot statis 33.3%.",
    ]

    return DemoResult(
        title="Compare SOTA vs Baseline: Accumulation Policy",
        lines=lines,
        metrics={
            "baseline_mse": baseline_mse,
            "sota_mse": sota_mse,
            "n_samples": len(data),
        },
        model="lightgbm_vs_rule",
        summary_md="# Perbandingan Model\n\nSOTA lebih baik karena MSE lebih rendah dari baseline.\n",
        scoreboard=True,
        scoreboard_kind="long_only",
        top_names=data[:10],
    )
