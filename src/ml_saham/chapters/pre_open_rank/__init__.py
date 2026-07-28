"""Ch.16 Pre-open rank — IEV snapshots ranking."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect
from ml_saham.data.phase2_read import load_iev_snapshots

META = get_meta("pre-open-rank")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Indikasi harga equilibrium volume (IEV) menjelang pembukaan — ranking intraday.",
        "",
        "Opsi pendekatan",
        "  1) load_iev_snapshots — rank by IEV / rank kolom",
        "  2) Top names untuk sesi pembukaan (bukan EOD scoreboard)",
        "  3) Bandingkan dengan momentum EOD (chapter lain)",
        "",
        "Caveat",
        "  • IEV bukan harga eksekusi garanti",
        "  • Scoreboard kind: open_session (bukan long-only EOD)",
        "  • Data phase2 — bisa kosong di DB lama",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: scoreboard_kind=open_session.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        rows = load_iev_snapshots(conn, as_of=ctx.as_of, limit_dates=3)
        if not rows:
            raise ChapterDataError(
                "iev_snapshots kosong.",
                hint="ml-saham doctor",
            )

    latest_date = rows[0]["date"]
    day_rows = [r for r in rows if r["date"] == latest_date]
    day_rows.sort(key=lambda r: (r.get("rank") is None, r.get("rank") or 9999))

    top = []
    imbalances = []
    for r in day_rows[:15]:
        iev = r.get("iev")
        iep = r.get("iep")
        try:
            iev_f = float(iev) if iev is not None else None
            iep_f = float(iep) if iep is not None else None
        except (TypeError, ValueError):
            iev_f, iep_f = None, None

        imbalance_pct = None
        if iev_f is not None and iep_f is not None and iep_f > 0:
            imbalance_pct = (iev_f / iep_f - 1.0)
            imbalances.append(imbalance_pct)

        top.append(
            {
                "ticker": r["ticker"],
                "rank": r.get("rank"),
                "iev": iev_f,
                "iep": iep_f,
                "imbalance_pct": imbalance_pct,
                "date": latest_date,
            }
        )

    avg_imbalance = (sum(imbalances) / len(imbalances)) if imbalances else 0.0

    lines = [
        f"date={latest_date}  n={len(day_rows)}  source=iev_snapshots",
        "Scoreboard: open_session (pre-open, bukan EOD long-only).",
        f"Pre-open order imbalance (IEV vs IEP avg): {avg_imbalance:+.2%}",
        "",
        "Top IEV names:",
    ]
    for t in top[:10]:
        iev_txt = f"{t['iev']:.2f}" if t["iev"] is not None else "?"
        rank_txt = t["rank"] if t["rank"] is not None else "?"
        imb_txt = f"  imb={t['imbalance_pct']:+.2%}" if t["imbalance_pct"] is not None else ""
        lines.append(f"  #{rank_txt:<4} {t['ticker']:<6}  IEV={iev_txt}{imb_txt}")

    lines.append("")
    lines.append("Catatan: ranking ini untuk konteks sesi pembukaan —")
    lines.append("bandingkan dengan factor-score EOD di chapter terpisah.")

    metrics = {
        "date": latest_date,
        "n": len(day_rows),
        "mean_pre_open_imbalance": avg_imbalance,
        "scoreboard_kind": "open_session",
    }
    csv = ["date,rank,ticker,iev"] + [
        f"{t['date']},{t['rank']},{t['ticker']},{t['iev'] or ''}" for t in top
    ]
    return DemoResult(
        title="Pre-open rank · IEV top names",
        lines=lines,
        metrics=metrics,
        model="iev_rank",
        summary_md=f"# Pre-open rank\n\n{latest_date}: top IEV names.\n",
        scoreboard=True,
        scoreboard_kind="open_session",
        top_names=top,
        extra_files={"iev_top.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="iev_snapshots / pre-open pipeline ai-saham",
        bring_back="IEV rank + open_session scoreboard habit",
    )
