"""Ch.15 Earnings surprise — rank surprise vs forward return."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
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
from ml_saham.data.phase2_read import load_earnings
from ml_saham.eval.metrics import rank_ic

META = get_meta("earnings-surprise")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  EPS surprise vs ekspektasi — apakah rank-nya prediktif return berikutnya?",
        "",
        "Opsi pendekatan",
        "  1) Rank by eps_surprise_pct (atau proxy YoY bila estimate kosong)",
        "  2) Join forward return via panel (pick_as_of style)",
        "  3) Rank IC surprise vs subsequent return",
        "",
        "Caveat",
        "  • fetched_date ≠ announcement PIT — cek lookahead",
        "  • Cache pribadi kadang tanpa estimate → proxy YoY, bukan true surprise",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nPIT: selalu catat fetched_date vs signal_date.")
    return "\n".join(lines)


def _surprise_score(e: dict) -> tuple[float, str] | None:
    try:
        if e.get("eps_surprise_pct") is not None:
            return float(e["eps_surprise_pct"]), "eps_surprise_pct"
        act, est = e.get("eps_actual"), e.get("eps_estimate")
        if act is not None and est is not None and float(est) != 0:
            return (
                100.0 * (float(act) - float(est)) / abs(float(est)),
                "computed_vs_estimate",
            )
        if e.get("eps_yoy_change") is not None:
            return float(e["eps_yoy_change"]), "eps_yoy_change_proxy"
    except (TypeError, ValueError):
        return None
    return None


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        earnings = load_earnings(conn, uni)
        if not earnings:
            raise ChapterDataError(
                "earnings_cache kosong.",
                hint="ml-saham doctor",
            )
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)
        bench = ihsg_forward_return(conn, as_of=as_of, horizon=5)

    by_t: dict[str, dict] = {}
    score_kind = "eps_surprise_pct"
    for e in earnings:
        t = e.get("ticker")
        if not t:
            continue
        scored = _surprise_score(e)
        if scored is None:
            continue
        surp_f, kind = scored
        key = (int(e.get("year") or 0), int(e.get("quarter") or 0))
        prev = by_t.get(t)
        if prev is None or key > prev["_key"]:
            by_t[t] = {**e, "surprise": surp_f, "_key": key}
            score_kind = kind

    rows = [
        {
            "ticker": t,
            "surprise": e["surprise"],
            "fetched_date": e.get("fetched_date"),
            "fwd": float(fwd[t]),
        }
        for t, e in by_t.items()
        if t in fwd
    ]

    if len(rows) < 8:
        if len(by_t) < 8:
            raise ChapterDataError(f"Panel earnings terlalu kecil (n={len(by_t)}).")
        ranked = sorted(by_t.items(), key=lambda kv: kv[1]["surprise"], reverse=True)
        lines = [
            f"as_of={as_of}  n_surprise={len(by_t)}  score={score_kind}",
            "(forward join kosong — tampil rank saja)",
            "PIT note: fetched_date bisa AFTER announcement.",
            "",
            "Top surprise (tanpa fwd join):",
        ]
        for t, e in ranked[:10]:
            lines.append(
                f"  {t:<6} surprise={e['surprise']:+.1f}%  "
                f"fetched={e.get('fetched_date')}"
            )
        return DemoResult(
            title="Earnings surprise · rank (no fwd join)",
            lines=lines,
            metrics={
                "as_of": as_of,
                "n": len(by_t),
                "fwd_joined": False,
                "score_kind": score_kind,
            },
            model="eps_surprise_rank",
            summary_md="# Earnings surprise\n\nForward join thin; ranked only.\n",
            scoreboard=True,
            top_names=[
                {"ticker": t, "surprise": e["surprise"]} for t, e in ranked[:10]
            ],
        )

    scores = [r["surprise"] for r in rows]
    rets = maybe_haircut([r["fwd"] for r in rows], with_costs=ctx.with_costs)
    ic = rank_ic(scores, rets)
    order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)

    lines = [
        f"as_of={as_of}  n={len(rows)}  horizon=5d  score={score_kind}",
        f"Rank IC ({score_kind} vs fwd): {ic:+.3f}",
        "PIT note: fetched_date di earnings_cache bisa AFTER announcement —",
        "jangan anggap otomatis point-in-time.",
    ]
    if bench is not None:
        lines.append(f"IHSG fwd 5d: {bench:+.2%}")
    lines.append("")
    lines.append("Top surprise names:")
    for i in order[:8]:
        r = rows[i]
        lines.append(
            f"  {r['ticker']:<6} surprise={r['surprise']:+.1f}%  "
            f"fwd={rets[i]:+.2%}  fetched={r.get('fetched_date') or '?'}"
        )

    top = [
        {"ticker": rows[i]["ticker"], "surprise": rows[i]["surprise"], "fwd": rets[i]}
        for i in order[:10]
    ]
    return DemoResult(
        title="Earnings surprise · rank IC",
        lines=lines,
        metrics={
            "as_of": as_of,
            "n": len(rows),
            "rank_ic_surprise": ic,
            "benchmark_return": bench,
            "score_kind": score_kind,
        },
        model="eps_surprise_rank",
        summary_md=f"# Earnings surprise\n\nIC={ic:.3f}. score={score_kind}.\n",
        scoreboard=True,
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="earnings_cache / surprise pipeline ai-saham",
        bring_back="surprise (atau YoY proxy) rank IC + fetched_date PIT habit",
    )
