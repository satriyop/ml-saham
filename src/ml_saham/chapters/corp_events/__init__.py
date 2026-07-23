"""Ch.14 Corp events — event study around ex_date."""

from __future__ import annotations

from collections import Counter, defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.data.phase2_read import load_corp_actions

META = get_meta("corp-events")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Dividen, stock split, rights — peristiwa korporasi mengubah return path.",
        "",
        "Opsi pendekatan",
        "  1) Event study: avg forward return sekitar ex_date",
        "  2) Count by event_type",
        "  3) Rule score sederhana (tipe event → prior)",
        "",
        "Caveat",
        "  • ex_date adjustment bisa belum sempurna di harga",
        "  • Sample kecil per tipe event",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_corp_actions dari corp_action_cache.")
    return "\n".join(lines)


def _fwd_around(
    by_t: dict[str, list[tuple[str, float]]], ticker: str, ex_date: str, horizon: int = 5
) -> float | None:
    series = by_t.get(ticker)
    if not series:
        return None
    series = sorted(series, key=lambda x: x[0])
    dates = [d for d, _ in series]
    if ex_date not in dates:
        idxs = [i for i, d in enumerate(dates) if d <= ex_date]
        if not idxs:
            return None
        i0 = idxs[-1]
    else:
        i0 = dates.index(ex_date)
    i1 = i0 + horizon
    if i1 >= len(series):
        return None
    c0, c1 = series[i0][1], series[i1][1]
    if c0 == 0:
        return None
    return (c1 / c0) - 1.0


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        events = load_corp_actions(conn, uni)
        if not events:
            raise ChapterDataError(
                "corp_action_cache / corporate_action_events kosong.",
                hint="ml-saham doctor",
            )
        candles = load_candles(conn, uni)

    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))

    type_counts = Counter(str(e.get("event_type", "unknown")) for e in events)
    fwd_by_type: dict[str, list[float]] = defaultdict(list)
    scored: list[dict] = []

    for e in events:
        t = e.get("ticker")
        ex = e.get("ex_date")
        etype = str(e.get("event_type", "unknown"))
        if not t or not ex:
            continue
        fwd = _fwd_around(by_t, t, ex, horizon=5)
        if fwd is None:
            continue
        fwd_by_type[etype].append(fwd)
        rule = 1.0 if "dividend" in etype.lower() else 0.5
        scored.append({"ticker": t, "event_type": etype, "ex_date": ex, "fwd": fwd, "score": rule})

    if not scored:
        raise ChapterDataError("Tidak ada event dengan forward return valid.")

    lines = [
        f"events={len(events)}  with_fwd={len(scored)}  universe={len(uni)}",
        "",
        "Count by event_type:",
    ]
    for et, cnt in type_counts.most_common(8):
        lines.append(f"  {et}: {cnt}")

    lines.append("")
    lines.append("Avg forward 5d return by event_type:")
    for et, rets in sorted(fwd_by_type.items(), key=lambda x: -len(x[1])):
        avg = sum(rets) / len(rets)
        lines.append(f"  {et:<20} n={len(rets):3d}  mean_fwd={avg:+.2%}")

    overall = sum(s["fwd"] for s in scored) / len(scored)
    lines.append("")
    lines.append(f"Overall event-study mean fwd: {overall:+.2%}")
    lines.append("Rule score: dividend-like=1.0, lainnya=0.5 (demo kasar).")

    top = sorted(scored, key=lambda s: s["score"], reverse=True)[:10]
    metrics = {
        "n_events": len(events),
        "n_with_fwd": len(scored),
        "type_counts": dict(type_counts),
        "mean_fwd_overall": overall,
    }
    return DemoResult(
        title="Corp events · event study",
        lines=lines,
        metrics=metrics,
        model="event_study_rule",
        summary_md=f"# Corp events\n\n{len(scored)} events with fwd. mean={overall:+.2%}.\n",
        scoreboard=True,
        top_names=top,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="corp_action_cache / corporate_action_events di ai-saham",
        bring_back="event study + ex_date hygiene habit",
    )
