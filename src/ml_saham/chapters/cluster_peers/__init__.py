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
        "  1) HDBSCAN + UMAP (SOTA, default)",
        "  2) k-means pada vektor return harian singkat (baseline, compare)",
        "",
        "Caveat",
        "  • Cluster ≠ rekomendasi beli; hanya kemiripan historis",
        "  • Sector label dari meta = konteks, bukan ground truth mutlak",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}  |  ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: deepdive boleh menyinggung sector diagnostics ai-saham.")
    return "\n".join(lines)


def _load_data_aligned(ctx: ChapterContext, window: int = 40):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=40)
        if len(uni) < 8:
            raise ChapterDataError(f"Universe terlalu kecil untuk cluster (n={len(uni)}).")
        candles = load_candles(conn, uni)
        sectors = load_sector_map(conn)

    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))

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
    return keep, X_rows, sectors, window


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.cluster import HDBSCAN
        import umap
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn>=1.3 dan umap-learn: pip install scikit-learn umap-learn") from exc

    keep, X_rows, sectors, window = _load_data_aligned(ctx)
    X = StandardScaler().fit_transform(np.array(X_rows, dtype=float))
    
    reducer = umap.UMAP(n_components=2, random_state=42)
    coords = reducer.fit_transform(X)
    
    hdb = HDBSCAN(min_cluster_size=2)
    labels = hdb.fit_predict(coords)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    lines = [
        f"n={len(keep)} tickers  window={window}d  k={n_clusters} (HDBSCAN)",
        "",
        "Clusters (HDBSCAN) · contoh anggota + sector:",
    ]
    by_c: dict[int, list[str]] = defaultdict(list)
    for t, lab in zip(keep, labels, strict=True):
        by_c[int(lab)].append(t)
    
    for c in sorted(by_c, key=lambda x: x if x != -1 else 999):
        members = by_c[c][:6]
        sec_bits = [f"{t}:{sectors.get(t, '?')[:16]}" for t in members]
        c_name = f"C{c}" if c != -1 else "Noise"
        lines.append(f"  {c_name} ({len(by_c[c])}): " + "; ".join(sec_bits))

    metrics = {
        "n_tickers": len(keep),
        "n_clusters": n_clusters,
        "window": window,
        "clusters": {str(c): by_c[c] for c in by_c},
    }
    csv = ["ticker,cluster,umap1,umap2,sector"]
    for i, t in enumerate(keep):
        csv.append(
            f"{t},{int(labels[i])},{coords[i, 0]:.6f},{coords[i, 1]:.6f},{sectors.get(t, '')}"
        )
    return DemoResult(
        title="Cluster peers · HDBSCAN + UMAP",
        lines=lines,
        metrics=metrics,
        model=f"hdbscan_umap_k{n_clusters}",
        summary_md=(
            f"# Cluster peers (SOTA)\n\nk={n_clusters} (HDBSCAN on UMAP), window={window}.\n"
        ),
        scoreboard=True,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        from sklearn.cluster import HDBSCAN, KMeans
        import umap
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn>=1.3 dan umap-learn: pip install scikit-learn umap-learn") from exc

    keep, X_rows, sectors, window = _load_data_aligned(ctx)
    X = StandardScaler().fit_transform(np.array(X_rows, dtype=float))
    
    # Baseline: KMeans
    n_clusters_km = min(5, max(2, len(keep) // 5))
    km = KMeans(n_clusters=n_clusters_km, random_state=42, n_init=10)
    labels_km = km.fit_predict(X)
    sil_km = float(silhouette_score(X, labels_km)) if len(set(labels_km)) > 1 else 0.0
    
    # SOTA: UMAP + HDBSCAN
    reducer = umap.UMAP(n_components=2, random_state=42)
    coords = reducer.fit_transform(X)
    hdb = HDBSCAN(min_cluster_size=2)
    labels_hdb = hdb.fit_predict(coords)
    n_clusters_hdb = len(set(labels_hdb)) - (1 if -1 in labels_hdb else 0)
    
    mask_hdb = labels_hdb != -1
    if len(set(labels_hdb[mask_hdb])) > 1:
        sil_hdb = float(silhouette_score(X[mask_hdb], labels_hdb[mask_hdb]))
    else:
        sil_hdb = 0.0

    lines = [
        f"n={len(keep)} tickers  window={window}d",
        "",
        "--- Baseline (k-means) ---",
        f"k={n_clusters_km}, Silhouette={sil_km:+.3f}",
        "",
        "--- SOTA (HDBSCAN + UMAP) ---",
        f"k={n_clusters_hdb} (tanpa noise), Silhouette={sil_hdb:+.3f}",
    ]
    
    metrics = {
        "n_tickers": len(keep),
        "window": window,
        "kmeans": {
            "n_clusters": n_clusters_km,
            "silhouette": sil_km,
        },
        "hdbscan": {
            "n_clusters": n_clusters_hdb,
            "silhouette": sil_hdb,
            "n_noise": int((~mask_hdb).sum()),
        }
    }
    
    csv = ["ticker,cluster_kmeans,cluster_hdbscan,umap1,umap2,sector"]
    for i, t in enumerate(keep):
        csv.append(
            f"{t},{int(labels_km[i])},{int(labels_hdb[i])},"
            f"{coords[i, 0]:.6f},{coords[i, 1]:.6f},{sectors.get(t, '')}"
        )
        
    return DemoResult(
        title="Cluster peers · HDBSCAN vs KMeans",
        lines=lines,
        metrics=metrics,
        model="hdbscan_vs_kmeans",
        summary_md=(
            f"# Cluster peers (Compare)\n\nK-means Silhouette: {sil_km:.3f}. HDBSCAN Silhouette: {sil_hdb:.3f}.\n"
        ),
        scoreboard=True,
        extra_files={"compare.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="sector-context diagnostics di ai-saham",
        bring_back="peer clusters sebagai sanity check diversifikasi / sektor bias",
    )
