"""Ch.11 Market regime — phase2 observations + GMM on IHSG."""

from __future__ import annotations

import math
from collections import Counter

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.data.phase2_read import load_regime_observations

META = get_meta("market-regime")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Rezim pasar (risk-on/off, vol tinggi/rendah) mengubah efektivitas sinyal.",
        "",
        "Opsi pendekatan",
        "  1) Baca regime_observations dari ai-saham (jika ada)",
        "  2) GMM unsupervised pada return+vol IHSG",
        "  3) Bandingkan forward IHSG per rezim",
        "",
        "Caveat",
        "  • Label rezim unsupervised ≠ ground truth",
        "  • Regime shift — parameter lama bisa basi",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: prefer load_regime_observations bila tabel ada.")
    return "\n".join(lines)


def _ihsg_features(conn) -> tuple[list[str], list[list[float]], list[float]]:
    rows = sorted(load_candles(conn, ["IHSG"]), key=lambda r: r["date"])
    if len(rows) < 60:
        raise ChapterDataError(f"IHSG history terlalu pendek (n={len(rows)}).")
    dates, feats, fwd5 = [], [], []
    closes = [float(r["close"]) for r in rows]
    for i in range(21, len(closes) - 5):
        rets = [math.log(closes[j] / closes[j - 1]) for j in range(i - 19, i + 1)]
        mean = sum(rets) / len(rets)
        vol = math.sqrt(sum((x - mean) ** 2 for x in rets) / len(rets))
        ret20 = closes[i] / closes[i - 20] - 1.0
        fwd = closes[i + 5] / closes[i] - 1.0
        dates.append(rows[i]["date"])
        feats.append([ret20, vol])
        fwd5.append(fwd)
    return dates, feats, fwd5


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.mixture import GaussianMixture
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    lines: list[str] = []
    metrics: dict = {}

    with connect(ctx.db_path) as conn:
        obs = load_regime_observations(conn, limit=60)
        if obs:
            regimes = [str(r.get("regime", "?")) for r in obs]
            counts = Counter(regimes)
            lines.append("regime_observations (phase2):")
            for reg, cnt in counts.most_common():
                lines.append(f"  {reg}: {cnt}")
            recent = obs[:5]
            lines.append("")
            lines.append("Recent observations:")
            for r in recent:
                d = r.get("observation_date", "?")
                reg = r.get("regime", "?")
                f5 = r.get("forward_ihsg_return_5d")
                ftxt = f"  fwd5d={float(f5):+.2%}" if f5 is not None else ""
                lines.append(f"  {d}  regime={reg}{ftxt}")
            metrics["obs_n"] = len(obs)
            metrics["obs_regimes"] = dict(counts)

        dates, feats, fwd5 = _ihsg_features(conn)

    X = np.array(feats)
    gmm = GaussianMixture(n_components=3, random_state=42, n_init=5)
    labels = gmm.fit_predict(X)
    gmm_counts = Counter(int(l) for l in labels)

    lines.append("")
    lines.append("GMM on IHSG (return20 + vol20):")
    for k in sorted(gmm_counts):
        idx = [i for i, l in enumerate(labels) if l == k]
        avg_fwd = sum(fwd5[i] for i in idx) / len(idx)
        avg_ret = sum(feats[i][0] for i in idx) / len(idx)
        avg_vol = sum(feats[i][1] for i in idx) / len(idx)
        lines.append(
            f"  cluster={k}  n={len(idx)}  "
            f"mean_ret20={avg_ret:+.2%}  vol={avg_vol:.4f}  "
            f"mean_fwd5d={avg_fwd:+.2%}"
        )

    last_label = int(labels[-1])
    lines.append("")
    lines.append(
        f"Latest GMM cluster={last_label}  date={dates[-1]}  "
        f"fwd5d={fwd5[-1]:+.2%}"
    )
    lines.append("Catatan: cluster unsupervised — interpretasi manual.")

    metrics.update(
        {
            "gmm_n": len(labels),
            "gmm_clusters": dict(gmm_counts),
            "latest_cluster": last_label,
            "latest_date": dates[-1],
        }
    )
    return DemoResult(
        title="Market regime · observations + GMM",
        lines=lines,
        metrics=metrics,
        model="gmm_ihsg_3",
        summary_md="# Market regime\n\nPhase2 observations + GMM IHSG clusters.\n",
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="regime_observations / regime engine di ai-saham",
        bring_back="rezim label + forward IHSG sanity check habit",
    )
