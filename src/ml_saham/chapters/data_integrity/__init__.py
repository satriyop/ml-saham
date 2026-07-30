"""Ch.45 Data integrity — observation health & data-plane honesty for challenges."""

from __future__ import annotations

from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, CompareResult, DemoResult
from ml_saham.data.doctor_checks import (
    format_doctor_report,
    integrity_score,
    run_doctor,
)

META = get_meta("data-integrity")

def explore_text(*, verbose: bool = False) -> str:
    # Learning axis: Indonesian narrative
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Challenge terhadap faktor ai-saham hanya jujur jika data plane sehat:",
        "  tabel ada, rentang tanggal selaras, observation (learning_observations)",
        "  cukup untuk ACCUM / PRE_OPEN, dan fundamentals punya fetched_date yang masuk akal.",
        "",
        "Opsi pendekatan",
        "  1) Coverage doctor (tabel ada/tidak) — baseline kasar",
        "  2) Integrity score (overlap tanggal, observation counts, PIT snapshots) — default lab",
        "",
        "Caveat",
        "  • Ini bukan model harga; ini gerbang kepercayaan sebelum challenge engine",
        "  • Laporan compare/challenge untuk topik ini: English (product axis)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham vet",
        f"         ml-saham compare {META.slug} --baseline coverage --against integrity",
        f"         ml-saham doctor --deep",
    ]
    if verbose:
        lines.append("\nPeta engine→tabel: docs/engine_factor_map.md")
    return "\n".join(lines)

def run_demo(ctx: ChapterContext) -> DemoResult:
    report = run_doctor(ctx.db_path, deep=True)
    score = integrity_score(report)
    # Learning-facing demo can mix; keep lines mostly EN for consistency with challenge
    lines = [
        f"DB: {ctx.db_path}",
        f"MVP hard OK: {report.mvp_hard_ok}",
        f"Integrity status: {score['status']}  score={score['score']:.2%}  "
        f"(ok={score['n_ok']}/{score['n_total']}, partial={score['n_partial']})",
        "",
        "Integrity items:",
    ]
    for item in report.integrity.items:
        soft = "" if item.hard else " (soft)"
        lines.append(f"  {item.name}: {item.status}{soft}  {item.detail}")
    lines.extend(
        [
            "",
            "Remediation:",
            *[f"  - {r}" for r in report.remediation[:6]],
        ]
    )
    return DemoResult(
        title="Data integrity · observation & plane health",
        lines=lines,
        metrics={
            "integrity_score": score["score"],
            "mvp_hard_ok": report.mvp_hard_ok,
            **{k: score[k] for k in ("n_ok", "n_partial", "n_total", "status")},
        },
        model="integrity_audit",
        summary_md=(
            "# Data integrity\n\n"
            f"Integrity score={score['score']:.2%} status={score['status']}.\n"
            "Use before engine challenge.\n"
        ),
        scoreboard=False,
        scoreboard_kind="none",
    )

def run_compare(ctx: ChapterContext, **kwargs) -> CompareResult:
    """English challenge report: coverage baseline vs integrity score."""
    report = run_doctor(ctx.db_path, deep=True)
    score = integrity_score(report)

    coverage_ok = 1.0 if report.mvp_hard_ok else 0.0
    integrity = float(score["score"])

    lines = [
        "Data integrity challenge (ai-saham data plane)",
        f"DB: {report.db_path}",
        "",
        f"Baseline (coverage / MVP hard): {coverage_ok:.0%}  "
        f"({'PASS' if coverage_ok >= 1.0 else 'FAIL'})",
        f"Against (integrity score):      {integrity:.2%}  "
        f"(ok={score['n_ok']} partial={score['n_partial']} total={score['n_total']})",
        "",
        "Integrity checklist:",
    ]
    for item in report.integrity.items:
        lines.append(f"  - {item.name}: {item.status} — {item.detail}")

    if report.remediation:
        lines.append("")
        lines.append("Remediation:")
        for r in report.remediation[:8]:
            lines.append(f"  - {r}")

    winner = (
        "integrity"
        if integrity > coverage_ok
        else ("coverage" if coverage_ok > integrity else "tie")
    )
    compare = {
        "baseline": {"id": "coverage", "score": coverage_ok},
        "against": {"id": "integrity", "score": integrity},
        "against_metrics": {
            "integrity_score": integrity,
            "n_ok": score["n_ok"],
            "n_partial": score["n_partial"],
            "n_total": score["n_total"],
        },
        "baseline_metrics": {"mvp_hard_ok": report.mvp_hard_ok, "score": coverage_ok},
    }
    return CompareResult(
        title="Data integrity · coverage vs deep integrity",
        lines=lines,
        metrics={
            "coverage_score": coverage_ok,
            "integrity_score": integrity,
            "mvp_hard_ok": report.mvp_hard_ok,
        },
        compare=compare,
        model="coverage_vs_integrity",
        summary_md=(
            "# Data integrity compare\n\n"
            f"Coverage (MVP hard)={coverage_ok:.0%}; integrity={integrity:.2%}.\n"
            "Gate engine challenges when integrity is thin.\n"
        ),
        scoreboard=False,
        winner=winner,
        winner_reason=(
            "Integrity score reflects observation health and date overlap, "
            "not just table presence."
        ),
    )

