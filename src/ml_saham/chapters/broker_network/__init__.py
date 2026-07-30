"""Ch.24 Broker Network — deteksi sindikasi broker (Graph ML)."""

from __future__ import annotations

import logging
from typing import Any

from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import pick_as_of, resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
from ml_saham.data.aisaham_read import connect, table_exists

META = get_meta("broker-network")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Mendeteksi sindikasi atau pergerakan bersama antar broker (coordinated rings)",
        "  untuk melihat siapa yang bergerak dalam kelompok yang sama.",
        "",
        "Opsi pendekatan",
        "  1) Graph ML / NetworkX Centrality Algorithms (default)",
        "     (PageRank, Eigenvector, Betweenness centrality pada jaringan transaksi/co-occurrence).",
        "  2) Simple node volume / degree centrality (baseline/compare).",
        "",
        "Caveat",
        "  • Butuh broker_daily_flow atau data transaksi broker (co-occurrence).",
        "  • Kompleksitas tinggi (Graph ML).",
        "  • Bukan bukti hukum manipulasi pasar, hanya klastering kemiripan aksi.",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Compare: ml-saham compare {META.slug} --baseline degree --against pagerank",
    ]
    if verbose:
        lines.append(
            "\nCatatan: Analisis `broker_daily_flow` network lebih dalam (manual / compare)."
        )
    return "\n".join(lines)

def _build_network(ctx: ChapterContext):
    """Build co-occurrence network from broker_daily_flow (preferred) or compatible tables."""
    from collections import defaultdict

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=10)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        ph = ",".join("?" * len(uni))
        rows: list = []

        if table_exists(conn, "broker_daily_flow"):
            cur = conn.execute(
                f"""
                SELECT date, ticker, broker_code, net_value
                FROM broker_daily_flow
                WHERE date <= ? AND ticker IN ({ph})
                ORDER BY date DESC LIMIT 4000
                """,
                [as_of, *uni],
            )
            for date_str, ticker, broker_code, net_value in cur.fetchall():
                rows.append((date_str, ticker, broker_code, float(net_value or 0.0), 0.0))
        elif table_exists(conn, "broker_summaries"):
            # Optional wide schema used by some caches (broker_code + bval/sval)
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(broker_summaries)").fetchall()
            }
            if {"broker_code", "bval", "sval"} <= cols:
                cur = conn.execute(
                    f"""
                    SELECT date, ticker, broker_code, bval, sval
                    FROM broker_summaries
                    WHERE date <= ? AND ticker IN ({ph})
                    ORDER BY date DESC LIMIT 4000
                    """,
                    [as_of, *uni],
                )
                rows = list(cur.fetchall())
            else:
                raise ChapterDataError(
                    "broker_summaries ada tapi tanpa broker_code; "
                    "butuh broker_daily_flow untuk graph challenge.",
                    hint="Seed broker_daily_flow atau jalankan fetch broker detail di ai-saham.",
                )
        else:
            raise ChapterDataError(
                "Tabel broker_daily_flow / broker_summaries tidak ditemukan."
            )

    if not rows:
        raise ChapterDataError("Tidak ada baris broker flow untuk membentuk network.")

    day_ticker_buyers = defaultdict(list)

    for r in rows:
        date_str, ticker, broker_code, bval, sval = r
        net = (bval or 0) - (sval or 0)
        if net > 0 and broker_code:
            day_ticker_buyers[(date_str, ticker)].append(str(broker_code))
            
    edges = defaultdict(int)
    nodes = set()
    for (d, t), buyers in day_ticker_buyers.items():
        for i in range(len(buyers)):
            nodes.add(buyers[i])
            for j in range(i+1, len(buyers)):
                b1, b2 = buyers[i], buyers[j]
                if b1 > b2:
                    b1, b2 = b2, b1
                edges[(b1, b2)] += 1
                nodes.add(b2)
                
    if not nodes:
        raise ChapterDataError("Tidak cukup co-occurrence net-buy untuk membentuk jaringan.")
        
    return as_of, nodes, edges

def _learned_centrality(nodes: set, edges: dict, model_type: str = "pagerank"):
    try:
        import networkx as nx
    except ImportError as exc:
        raise ChapterError("Butuh networkx: pip install networkx") from exc
        
    G = nx.Graph()
    for n in nodes:
        G.add_node(n)
    for (u, v), w in edges.items():
        G.add_edge(u, v, weight=w)
        
    if len(G.nodes) == 0:
        return {}, "empty", {}

    if model_type == "degree":
        # Baseline: simple node degree (weighted)
        scores = {n: val for n, val in G.degree(weight="weight")}
        model_name = "Degree Centrality"
    elif model_type in ("pagerank", "sota", "networkx"):
        # Default: PageRank
        try:
            scores = nx.pagerank(G, weight="weight")
            model_name = "PageRank (Graph ML)"
        except Exception:
            scores = {n: val for n, val in nx.degree_centrality(G).items()}
            model_name = "Degree Centrality (Fallback)"
    elif model_type == "betweenness":
        # Alternatif default
        scores = nx.betweenness_centrality(G, weight="weight")
        model_name = "Betweenness Centrality"
    else:
        scores = {n: val for n, val in G.degree()}
        model_name = "Simple Degree"
        
    return scores, model_name, G

def run_demo(ctx: ChapterContext) -> DemoResult:
    as_of, nodes, edges = _build_network(ctx)
    scores, model_name, G = _learned_centrality(nodes, edges, model_type="pagerank")
    
    order = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    top = [
        {
            "broker": b,
            "score": scores[b],
            "degree": G.degree(b, weight="weight")
        }
        for b in order[:10]
    ]
    
    lines = [
        f"as_of={as_of}  nodes={len(nodes)}  edges={len(edges)}",
        f"Model: {model_name} (Default Graph ML)",
        "",
        "Top Sindikasi / Sentralitas Broker:"
    ]
    for t in top:
        lines.append(f"  Broker {t['broker']:<4} : score={t['score']:.4f}  (weight-degree={t['degree']})")
        
    metrics = {
        "as_of": as_of,
        "nodes": len(nodes),
        "edges": len(edges),
        "model": model_name,
    }
    
    csv = ["broker,score,weight_degree"] + [
        f"{t['broker']},{t['score']:.6f},{t['degree']}"
        for t in top
    ]
    
    return DemoResult(
        title=f"Broker Network · {model_name}",
        lines=lines,
        metrics=metrics,
        model=model_name,
        summary_md=(
            f"# Broker Network\n\n"
            f"as_of={as_of}. default model: `{model_name}`.\n"
            f"Menganalisis {len(nodes)} node broker dan {len(edges)} edge co-occurrence.\n"
        ),
        scoreboard=False,
        top_names=[t["broker"] for t in top],
        extra_files={"top_brokers.csv": "\n".join(csv) + "\n"},
    )

def run_compare(ctx: ChapterContext, *, baseline: str, against: str) -> CompareResult:
    as_of, nodes, edges = _build_network(ctx)
    
    base_scores, base_name, _ = _learned_centrality(nodes, edges, model_type=baseline)
    ag_scores, ag_name, _ = _learned_centrality(nodes, edges, model_type=against)
    
    top_b = sorted(base_scores.keys(), key=lambda x: base_scores[x], reverse=True)[:10]
    top_a = sorted(ag_scores.keys(), key=lambda x: ag_scores[x], reverse=True)[:10]
    
    overlap = len(set(top_b) & set(top_a))
    
    lines = [
        f"as_of={as_of}  nodes={len(nodes)}  edges={len(edges)}",
        f"{baseline}: {base_name}",
        f"{against}: {ag_name}",
        f"Overlap top-10 brokers: {overlap}",
        "",
        "Top 5 Baseline:"
    ]
    for b in top_b[:5]:
        lines.append(f"  {b}: {base_scores[b]:.4f}")
        
    lines.append("Top 5 Against (default):")
    for b in top_a[:5]:
        lines.append(f"  {b}: {ag_scores[b]:.4f}")

    compare = {
        "baseline": {"id": baseline, "model": base_name, "top10": top_b},
        "against": {"id": against, "model": ag_name, "top10": top_a},
        "as_of": as_of,
        "nodes": len(nodes),
        "edges": len(edges),
    }
    
    return CompareResult(
        title=f"Compare · {baseline} vs {against}",
        lines=lines,
        metrics={"overlap": overlap},
        compare=compare,
        model=f"{baseline}_vs_{against}",
        summary_md=(
            f"# Compare broker-network\n\n"
            f"`{baseline}` ({base_name}) vs `{against}` ({ag_name}) as_of={as_of}.\n"
        ),
        scoreboard=False,
    )

