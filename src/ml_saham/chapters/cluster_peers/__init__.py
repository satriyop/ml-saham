"""Ch.5 Cluster peers — saham yang bergerak mirip."""

from __future__ import annotations

from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles, load_sector_map

META = get_meta("cluster-peers")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Saham mana yang 'bergerak mirip'? Berguna untuk peers, diversifikasi,",
        "  dan cek apakah model hanya menghafal satu sektor.",
        "",
        "Opsi pendekatan",
        "  1) k-means pada vektor return harian singkat",
        "  2) Hierarchical clustering (agglomerative)",
        "  3) PCA 2D untuk visualisasi ringkas (terminal: print loadings)",
        "",
        "Caveat",
        "  • Cluster ≠ rekomendasi beli; hanya kemiripan historis",
        "  • Sector label dari meta = konteks, bukan ground truth mutlak",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: deepdive boleh menyinggung sector diagnostics ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.cluster import AgglomerativeClustering, KMeans
        from sklearn.decomposition import PCA
        from sklearn.metrics import davies_bouldin_score, silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=40)
        if len(uni) < 8:
            raise ChapterDataError(f"Universe terlalu kecil untuk cluster (n={len(uni)}).")
        candles = load_candles(conn, uni)
        sectors = load_sector_map(conn)

    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))

    # Align last N returns on common calendar
    window = 40
    series: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    for t, rows in by_t.items():
        rows = sorted(rows, key=lambda x: x[0])
        if len(rows) < window + 5:
            continue
        rets: dict[str, float] = {}
        for i in range(1, len(rows)):
            c0, c1 = rows[i - 1][1], rows[i][1]
            if c0 > 0:
                rets[rows[i][0]] = c1 / c0 - 1.0
        series[t] = rets
        all_dates.update(rets)

    dates = sorted(all_dates)[-window:]
    tickers = sorted(series)
    X_rows = []
    keep = []
    for t in tickers:
        vec = [series[t].get(d) for d in dates]
        if any(v is None for v in vec):
            continue
        X_rows.append(vec)
        keep.append(t)
    if len(keep) < 8:
        raise ChapterDataError(
            f"Panel return teralign terlalu kecil (n={len(keep)}). Perlu lebih banyak history."
        )

    X = StandardScaler().fit_transform(np.array(X_rows, dtype=float))
    n_clusters = min(5, max(2, len(keep) // 5))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels_km = km.fit_predict(X)
    agg = AgglomerativeClustering(n_clusters=n_clusters)
    labels_agg = agg.fit_predict(X)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)

    sil_score = float(silhouette_score(X, labels_km)) if len(set(labels_km)) > 1 else 0.0
    db_score = float(davies_bouldin_score(X, labels_km)) if len(set(labels_km)) > 1 else 0.0

    # agreement: same pair co-clustered?
    agree = 0
    total_pairs = 0
    for i in range(len(keep)):
        for j in range(i + 1, len(keep)):
            total_pairs += 1
            same_km = labels_km[i] == labels_km[j]
            same_agg = labels_agg[i] == labels_agg[j]
            if same_km == same_agg:
                agree += 1
    agree_rate = agree / total_pairs if total_pairs else 0.0

    lines = [
        f"n={len(keep)} tickers  window={window}d  k={n_clusters}",
        f"PCA var explained: {pca.explained_variance_ratio_[0]:.2%} / "
        f"{pca.explained_variance_ratio_[1]:.2%}",
        f"k-means vs hierarchical pair-agreement: {agree_rate:.1%}",
        f"Cluster diagnostics: Silhouette={sil_score:+.3f}  Davies-Bouldin={db_score:.3f}",
        "",
        "Clusters (k-means) · contoh anggota + sector:",
    ]
    by_c: dict[int, list[str]] = defaultdict(list)
    for t, lab in zip(keep, labels_km, strict=True):
        by_c[int(lab)].append(t)
    for c in sorted(by_c):
        members = by_c[c][:6]
        sec_bits = [f"{t}:{sectors.get(t, '?')[:16]}" for t in members]
        lines.append(f"  C{c} ({len(by_c[c])}): " + "; ".join(sec_bits))

    metrics = {
        "n_tickers": len(keep),
        "n_clusters": n_clusters,
        "window": window,
        "pair_agreement": agree_rate,
        "silhouette_score": sil_score,
        "davies_bouldin_score": db_score,
        "pca_var": pca.explained_variance_ratio_.tolist(),
        "clusters": {str(c): by_c[c] for c in by_c},
    }
    csv = ["ticker,cluster_kmeans,cluster_agg,pca1,pca2,sector"]
    for i, t in enumerate(keep):
        csv.append(
            f"{t},{int(labels_km[i])},{int(labels_agg[i])},"
            f"{coords[i, 0]:.6f},{coords[i, 1]:.6f},{sectors.get(t, '')}"
        )
    return DemoResult(
        title="Cluster peers · k-means + hierarchical + PCA",
        lines=lines,
        metrics=metrics,
        model=f"kmeans_k{n_clusters}",
        summary_md=(
            f"# Cluster peers\n\nk={n_clusters}, window={window}. "
            f"Pair agreement k-means vs agglomerative: {agree_rate:.1%}.\n"
        ),
        scoreboard=True,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="sector-context diagnostics di ai-saham",
        bring_back="peer clusters sebagai sanity check diversifikasi / sektor bias",
    )
