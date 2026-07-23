"""Ch.6 Broker & foreign flow — who ranks from flow."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import (
    foreign_net_nday,
    forward_returns_by_ticker,
    ihsg_forward_return,
    maybe_haircut,
    momentum_nday,
    pick_as_of,
    resolve_universe,
    zscore,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.doctor_checks import run_doctor
from ml_saham.eval.metrics import metrics_bundle, rank_ic

META = get_meta("broker-flow")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Ranking dari aliran *who*: net asing / broker summary — bukan volume burst",
        "  (volume anomaly = Ch.8). Fokus: siapa yang lebih agresif beli/jual.",
        "",
        "Opsi pendekatan",
        "  1) Aturan: N-hari foreign-net (value) → rank",
        "  2) z-score foreign-net silang saham",
        "  3) Cek inkremental vs momentum (apakah flow menambah info?)",
        "  4) Lab bandar/konsentrasi (opsional, bukan klaim smart-money)",
        "",
        "Caveat",
        "  • Butuh broker_summaries / foreign_flow_points — doctor hard-fail jika hilang",
        "  • Flow ≠ bukti manipulasi; ini ranking riset saja",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append(
            "\nDeepdive stub: komponen accum / foreign-flow score di ai-saham (manual)."
        )
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    report = run_doctor(ctx.db_path)
    hard_broker = [
        i
        for i in report.mvp.items
        if i.name in {"broker_summaries", "foreign_flow_points"} and i.hard
    ]
    if any(i.status != "ok" for i in hard_broker):
        detail = ", ".join(f"{i.name}={i.status}" for i in hard_broker)
        raise ChapterDataError(
            f"Data broker/foreign belum siap ({detail})."
        )

    with connect(ctx.db_path) as conn:
        if not table_exists(conn, "broker_summaries") and not table_exists(
            conn, "foreign_flow_points"
        ):
            raise ChapterDataError(
                "Tabel broker_summaries/foreign_flow_points hilang."
            )
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        flow = foreign_net_nday(conn, uni, as_of=as_of, window=5)
        mom = momentum_nday(conn, uni, as_of=as_of, window=20)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    tickers = sorted(set(flow) & set(fwd) & set(mom))
    if len(tickers) < 10:
        raise ChapterDataError(f"Panel flow terlalu kecil (n={len(tickers)}).")

    flow_vals = [flow[t] for t in tickers]
    flow_z = zscore(flow_vals)
    scores = [0.0 if z is None else float(z) for z in flow_z]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    mom_scores = [mom[t] for t in tickers]
    ic_flow = rank_ic(scores, rets)
    ic_mom = rank_ic(mom_scores, rets)
    # residual-ish: flow rank IC on names where momentum rank disagrees sign
    blend = [0.5 * scores[i] + 0.5 * float(zscore(mom_scores)[i] or 0) for i in range(len(tickers))]
    ic_blend = rank_ic(blend, rets)

    bundle = metrics_bundle(
        scores,
        rets,
        benchmark_return=bench,
        date_range=(as_of, as_of),
        n_tickers=len(tickers),
    )
    order = sorted(range(len(tickers)), key=lambda i: scores[i], reverse=True)
    top = [
        {
            "ticker": tickers[i],
            "score": scores[i],
            "flow_net_5d": flow[tickers[i]],
            "mom20": mom[tickers[i]],
            "fwd": rets[i],
        }
        for i in order[:10]
    ]
    lines = [
        f"as_of={as_of}  n={len(tickers)}  window_flow=5d  horizon=5d",
        f"Foreign-net z rank IC: {ic_flow:+.3f}",
        f"Momentum-20 rank IC:   {ic_mom:+.3f}",
        f"0.5 flow + 0.5 mom IC: {ic_blend:+.3f}  (cek inkremental kasar)",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
    lines.append("")
    lines.append("Top foreign-net z names:")
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} z={t['score']:+.2f}  "
            f"net5d={t['flow_net_5d']:.3g}  mom20={t['mom20']:+.2%}  "
            f"fwd={t['fwd']:+.2%}"
        )
    lines.append("")
    lines.append(
        "Catatan: lab konsentrasi/bandar opsional — bukan klaim smart-money."
    )

    metrics = {
        **bundle,
        "as_of": as_of,
        "rank_ic_flow": ic_flow,
        "rank_ic_momentum": ic_mom,
        "rank_ic_blend": ic_blend,
    }
    csv = ["ticker,score,flow_net_5d,mom20,fwd"] + [
        f"{t['ticker']},{t['score']:.6f},{t['flow_net_5d']:.6f},"
        f"{t['mom20']:.6f},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title="Broker flow · foreign-net rank",
        lines=lines,
        metrics=metrics,
        model="foreign_net_z_5d",
        summary_md=(
            f"# Broker flow\n\nas_of={as_of}. Foreign-net 5d z-score rank.\n"
            f"IC flow={ic_flow:.3f}, mom={ic_mom:.3f}, blend={ic_blend:.3f}.\n"
            "Bukan klaim smart-money.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="accum / foreign-flow score components, BCI (manual review)",
        bring_back="foreign-net rank IC + cek inkremental vs momentum",
    )
