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
        "  2) HMM (Hidden Markov Models) pada return+vol IHSG (SOTA/default)",
        "  3) GMM (Gaussian Mixture Model) unsupervised (Baseline/compare)",
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
        from hmmlearn.hmm import GaussianHMM
    except ImportError as exc:
        raise ChapterError("Butuh hmmlearn & numpy: pip install hmmlearn numpy") from exc

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
    hmm = GaussianHMM(n_components=3, random_state=42, n_iter=100)
    hmm.fit(X)
    raw_labels = hmm.predict(X)

    # Sort clusters by mean ret20 to give consistent semantic labels:
    # 0 = Bearish, 1 = Neutral/Sideways, 2 = Bullish
    cluster_means = {}
    for k in range(3):
        idx = [i for i, l in enumerate(raw_labels) if l == k]
        cluster_means[k] = np.mean([feats[i][0] for i in idx]) if idx else 0.0
    sorted_clusters = sorted(cluster_means, key=lambda k: cluster_means[k])
    label_map = {old_k: new_k for new_k, old_k in enumerate(sorted_clusters)}
    labels = [label_map[l] for l in raw_labels]
    state_names = {0: "Bearish", 1: "Neutral", 2: "Bullish"}

    hmm_counts = Counter(labels)

    lines.append("")
    lines.append("Gaussian HMM on IHSG (return20 + vol20):")
    for k in sorted(hmm_counts):
        idx = [i for i, l in enumerate(labels) if l == k]
        avg_fwd = sum(fwd5[i] for i in idx) / len(idx)
        avg_ret = sum(feats[i][0] for i in idx) / len(idx)
        avg_vol = sum(feats[i][1] for i in idx) / len(idx)
        lines.append(
            f"  state={k} ({state_names[k]:<7})  n={len(idx)}  "
            f"mean_ret20={avg_ret:+.2%}  vol={avg_vol:.4f}  "
            f"fwd_5d={avg_fwd:+.2%}"
        )

    last_label = labels[-1]
    raw_probs = hmm.predict_proba(X[-1:])[0]
    sorted_probs = [float(raw_probs[old_k]) for old_k in sorted_clusters]
    prob_str = ", ".join(f"{state_names[i]}:{p:.1%}" for i, p in enumerate(sorted_probs))

    lines.append("")
    lines.append(
        f"Latest HMM state={last_label} ({state_names[last_label]})  date={dates[-1]}  "
        f"fwd5d={fwd5[-1]:+.2%}"
    )
    lines.append(f"Latest regime probabilities: {prob_str}")
    lines.append("Catatan: cluster unsupervised — interpretasi manual.")

    metrics.update(
        {
            "hmm_n": len(labels),
            "hmm_clusters": dict(hmm_counts),
            "latest_cluster": last_label,
            "latest_state_name": state_names[last_label],
            "latest_date": dates[-1],
            "latest_probabilities": dict(zip(["Bearish", "Neutral", "Bullish"], sorted_probs, strict=True)),
        }
    )
    return DemoResult(
        title="Market regime · observations + Gaussian HMM",
        lines=lines,
        metrics=metrics,
        model="hmm_ihsg_3",
        summary_md=f"# Market regime\n\nLatest state={state_names[last_label]} ({sorted_probs[last_label]:.1%}).\n",
        scoreboard=True,
        scoreboard_kind="long_only",
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from hmmlearn.hmm import GaussianHMM
        from sklearn.mixture import GaussianMixture
    except ImportError as exc:
        raise ChapterError("Butuh hmmlearn, scikit-learn & numpy") from exc

    lines: list[str] = []
    metrics: dict = {}

    with connect(ctx.db_path) as conn:
        dates, feats, fwd5 = _ihsg_features(conn)

    X = np.array(feats)
    
    # Train SOTA (HMM)
    hmm = GaussianHMM(n_components=3, random_state=42, n_iter=100)
    hmm.fit(X)
    hmm_raw = hmm.predict(X)
    
    # Train Baseline (GMM)
    gmm = GaussianMixture(n_components=3, random_state=42, n_init=5)
    gmm_raw = gmm.fit_predict(X)
    
    def map_labels(raw_labels):
        c_means = {}
        for k in range(3):
            idx = [i for i, l in enumerate(raw_labels) if l == k]
            c_means[k] = np.mean([feats[i][0] for i in idx]) if idx else 0.0
        s_clusters = sorted(c_means, key=lambda k: c_means[k])
        l_map = {old_k: new_k for new_k, old_k in enumerate(s_clusters)}
        return [l_map[l] for l in raw_labels]
        
    hmm_labels = map_labels(hmm_raw)
    gmm_labels = map_labels(gmm_raw)
    
    state_names = {0: "Bearish", 1: "Neutral", 2: "Bullish"}
    
    lines.append("Perbandingan Market Regime: HMM (SOTA) vs GMM (Baseline)")
    lines.append("")
    
    for name, labels in [("HMM", hmm_labels), ("GMM", gmm_labels)]:
        lines.append(f"Model: {name}")
        counts = Counter(labels)
        for k in sorted(counts):
            idx = [i for i, l in enumerate(labels) if l == k]
            avg_fwd = sum(fwd5[i] for i in idx) / len(idx)
            avg_ret = sum(feats[i][0] for i in idx) / len(idx)
            avg_vol = sum(feats[i][1] for i in idx) / len(idx)
            lines.append(
                f"  state={k} ({state_names[k]:<7})  n={len(idx)}  "
                f"mean_ret20={avg_ret:+.2%}  vol={avg_vol:.4f}  "
                f"fwd_5d={avg_fwd:+.2%}"
            )
        lines.append("")
        
    metrics["hmm_counts"] = dict(Counter(hmm_labels))
    metrics["gmm_counts"] = dict(Counter(gmm_labels))

    return DemoResult(
        title="Market regime · HMM vs GMM",
        lines=lines,
        metrics=metrics,
        model="hmm_vs_gmm",
        summary_md="# Market regime Comparison\n\nComparing HMM vs GMM.",
        scoreboard=False,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="regime_observations / regime engine di ai-saham",
        bring_back="rezim label + forward IHSG sanity check habit",
    )
