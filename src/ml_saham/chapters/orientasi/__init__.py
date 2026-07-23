"""Ch.0 Orientasi — cara menilai hasil tanpa menipu diri."""

from __future__ import annotations

from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import (
    broker_summaries_date_range,
    candle_date_range,
    connect,
    has_ihsg,
    ticker_candle_count,
)
from ml_saham.data.doctor_checks import run_doctor
from ml_saham.data.universe import default_universe

META = get_meta("orientasi")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Bagaimana menilai hasil model saham tanpa menipu diri?",
        "  Di IDX, mudah sekali terlihat 'pintar' karena kebetulan bull market,",
        "  look-ahead (pakai info yang belum tersedia), atau lupa biaya.",
        "",
        "Tujuan chapter ini",
        "  1) Tahu skorboard default: long-only vs IHSG (gross + banner biaya)",
        "  2) Tahu PIT: fetched_date ≠ tanggal ekonomi fundamentals",
        "  3) Biasakan cek data dulu (`doctor`) sebelum demo chapter lain",
        "",
        "Opsi pendekatan (baseline kejujuran)",
        "  1) Buy & hold IHSG / universe equal-weight",
        "  2) Aturan tangan sederhana (nanti Ch.2)",
        "  3) Model ML — hanya berguna jika mengalahkan baseline dengan jujur",
        "",
        "Caveat (baca sebelum demo)",
        "  • Contoh PIT mainan: PE 'hari ini' dipakai untuk ranking minggu lalu",
        "    → itu look-ahead. Di DB kita, company_fundamentals punya fetched_date;",
        "    jangan samakan dengan tanggal laporan keuangan.",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya (default)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Detail (--verbose)",
                "  • Walk-forward penuh baru di Ch.12; di sini cukup kebiasaan dasar",
                "  • Artifact dari demo dipakai untuk audit pribadi, bukan live edge",
            ]
        )
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    report = run_doctor(ctx.db_path)
    lines = [
        f"DB: {ctx.db_path}",
        f"MVP hard OK: {'ya' if report.mvp_hard_ok else 'tidak'}",
        f"MVP status: {report.mvp.status}",
    ]
    if not report.db_exists:
        lines.append("File DB tidak ada — set --db atau ML_SAHAM_DB.")
        return DemoResult(
            title="Orientasi · status data",
            lines=lines,
            metrics={"mvp_hard_ok": False},
            model="status",
            summary_md="# Orientasi\n\nDB missing.\n",
            scoreboard=True,
        )

    with connect(ctx.db_path) as conn:
        cmin, cmax = candle_date_range(conn)
        bmin, bmax = broker_summaries_date_range(conn)
        uni = default_universe(conn)
        ihsg_n = ticker_candle_count(conn, "IHSG") if has_ihsg(conn) else 0

    lines.extend(
        [
            f"IHSG: {'ada' if ihsg_n else 'tidak'}  bars={ihsg_n}",
            f"Candles range: {cmin} .. {cmax}",
            f"Broker summaries range: {bmin} .. {bmax}",
            f"Universe default (LQ45∩cache): {len(uni)} tickers",
            f"Contoh: {', '.join(uni[:8])}{'…' if len(uni) > 8 else ''}",
            "",
            "Toy PIT (ingat ini):",
            "  Salah: pakai PE fetched 2026-07-01 untuk ranking tanggal 2025-01-15.",
            "  Lebih jujur: hanya pakai snapshot dengan fetched_date ≤ as_of.",
        ]
    )
    for item in report.mvp.items:
        soft = "" if item.hard else " (soft)"
        lines.append(f"  {item.name}: {item.status}{soft}")

    metrics = {
        "mvp_hard_ok": report.mvp_hard_ok,
        "mvp_status": report.mvp.status,
        "ihsg_bars": ihsg_n,
        "universe_n": len(uni),
        "candle_range": {"start": cmin, "end": cmax},
        "broker_range": {"start": bmin, "end": bmax},
        "n_tickers": len(uni),
    }
    summary = (
        "# Orientasi · demo\n\n"
        "Cek konektivitas DB, IHSG, universe, dan rentang tanggal.\n\n"
        "## PIT\n\n"
        "`fetched_date` pada fundamentals/shareholding adalah waktu cache, "
        "bukan tanggal ekonomi laporan.\n\n"
        "## Caveat\n\n"
        "- Bukan saran trading / investasi.\n"
        "- Skorboard default long-only vs IHSG + banner biaya.\n"
    )
    return DemoResult(
        title="Orientasi · status data",
        lines=lines,
        metrics=metrics,
        model="status",
        summary_md=summary,
        scoreboard=True,
    )
