"""Typer CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ml_saham import __version__
from ml_saham.artifacts import (
    ArtifactWriteRequest,
    ScoreboardMeta,
    resolve_artifacts_root,
    stub_demo_metrics,
    write_artifact_pack,
)
from ml_saham.chapters import get as get_chapter
from ml_saham.chapters import mvp_chapters
from ml_saham.chapters.registry import all_chapters
from ml_saham.cli.explore_view import explore_body, print_explore
from ml_saham.data.connection import resolve_db_path
from ml_saham.data.doctor_checks import format_doctor_report, run_doctor
from ml_saham.eval import costs_label, default_banners
from ml_saham.progress import mark, topic_flags

app = typer.Typer(
    name="ml-saham",
    help="Kursus ML problem-centric untuk pasar IDX (personal learning).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _phase_label(phase: str) -> str:
    return {
        "mvp": "MVP",
        "v1_1": "v1.1",
        "phase2": "phase-2",
        "optional": "opsional",
    }.get(phase, phase)


def _progress_cell(slug: str) -> str:
    flags = topic_flags(slug)
    bits = []
    if flags["explore"]:
        bits.append("E")
    if flags["demo"]:
        bits.append("D")
    if flags["deepdive"]:
        bits.append("DV")
    return "/".join(bits) if bits else "—"


@app.callback()
def main_callback(
    ctx: typer.Context,
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path SQLite (default: ML_SAHAM_DB atau ~/dev/ai-saham/data/db/data.db)",
        exists=False,
        dir_okay=False,
        file_okay=True,
        resolve_path=False,
    ),
    artifacts_dir: Optional[Path] = typer.Option(
        None,
        "--artifacts-dir",
        help="Root folder artifact (default: ML_SAHAM_ARTIFACTS atau ./artifacts)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=False,
    ),
) -> None:
    """Global options."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = resolve_db_path(db)
    ctx.obj["artifacts_dir"] = artifacts_dir


@app.command("chapters")
def chapters_cmd(
    all_phases: bool = typer.Option(
        False,
        "--all",
        help="Tampilkan semua chapter (default: sorot MVP + ringkas sisanya)",
    ),
) -> None:
    """Tampilkan jalur chapter dan progress."""
    table = Table(title="ml-saham chapters")
    table.add_column("#", justify="right")
    table.add_column("topic")
    table.add_column("phase")
    table.add_column("judul")
    table.add_column("progress", justify="center")

    rows = all_chapters() if all_phases else mvp_chapters()
    for ch in rows:
        table.add_row(
            str(ch.number),
            ch.slug,
            _phase_label(ch.phase),
            ch.title,
            _progress_cell(ch.slug),
        )
    console.print(table)
    if not all_phases:
        console.print(
            "\n[dim]MVP saja. Progress: E=explore D=demo DV=deepdive. "
            "Lihat semua: ml-saham chapters --all[/dim]"
        )


@app.command("status")
def status_cmd(ctx: typer.Context) -> None:
    """Ringkas DB + progress MVP."""
    db_path: Path = ctx.obj["db"]
    console.print(f"DB: {db_path}")
    console.print(f"Ada file: {'ya' if db_path.is_file() else 'tidak'}")
    console.print(f"Versi: {__version__}")
    console.print("\nProgress MVP:")
    for ch in mvp_chapters():
        console.print(f"  Ch.{ch.number} {ch.slug}: {_progress_cell(ch.slug)}")


@app.command("explore")
def explore_cmd(
    topic: str = typer.Argument(help="Topic slug, mis. factor-score"),
    no_pager: bool = typer.Option(
        False,
        "--no-pager",
        help="Cetak explore tanpa pager",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Tambah detail di bawah caveat",
    ),
) -> None:
    """Jelaskan masalah umum + opsi + caveat (belum train)."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    text = explore_body(ch, verbose=verbose)
    print_explore(console, text, use_pager=not no_pager)
    mark(topic, "explore")


@app.command("demo")
def demo_cmd(
    ctx: typer.Context,
    topic: str = typer.Argument(help="Topic slug"),
    with_costs: bool = typer.Option(
        False,
        "--with-costs",
        help="Terapkan haircut biaya sederhana pada metrik stub",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Jangan tulis artifact pack",
    ),
) -> None:
    """Jalankan demo pada data real."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    db_path: Path = ctx.obj["db"]
    console.print(f"[bold]Demo Ch.{ch.number} {ch.slug}[/bold]")
    console.print(f"Data     db={db_path}")
    console.print(
        "[yellow]Demo chapter belum diimplementasi "
        f"(Phase 3 — {ch.slug}); menulis artifact stub Phase 2.[/yellow]"
    )

    metrics = stub_demo_metrics(with_costs=with_costs)
    console.print(
        f"Stub metrics  rank_ic={metrics['rank_ic']:.4f}  n={metrics['n']}"
    )
    console.print()
    console.print(default_banners(with_costs=with_costs).render())

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="demo",
                db_path=db_path,
                model="stub",
                scoreboard=ScoreboardMeta(costs=costs_label(with_costs=with_costs)),
                summary_md=(
                    f"# Demo stub · {ch.slug}\n\n"
                    f"Phase 2 frame saja. Chapter {ch.number} belum punya "
                    f"`run_demo` real.\n\n"
                    f"- rank_ic (stub): {metrics['rank_ic']:.4f}\n"
                    f"- with_costs: {with_costs}\n\n"
                    "## Caveat\n\n"
                    "- Bukan saran trading / investasi.\n"
                    "- Metrik di metrics.json adalah toy data deterministik.\n"
                ),
                metrics=metrics,
            ),
            artifacts_root=root,
        )
        console.print(f"\nArtifact:  {pack.path}")

    mark(topic, "demo")


@app.command("compare")
def compare_cmd(
    ctx: typer.Context,
    topic: str = typer.Argument(help="Topic slug"),
    baseline: str = typer.Option(..., "--baseline", help="Baseline id"),
    against: str = typer.Option(..., "--against", help="Model pembanding"),
    with_costs: bool = typer.Option(
        False,
        "--with-costs",
        help="Terapkan haircut biaya sederhana pada metrik stub",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Jangan tulis artifact pack",
    ),
) -> None:
    """Bandingkan baseline vs model."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    db_path: Path = ctx.obj["db"]
    console.print(
        f"[yellow]Compare belum diimplementasi untuk {ch.slug} "
        f"({baseline} vs {against}); artifact stub Phase 2.[/yellow]"
    )
    base_m = stub_demo_metrics(with_costs=with_costs)
    # Slightly weaker toy IC for "against" so compare.json is non-trivial
    against_m = dict(base_m)
    against_m["rank_ic"] = float(base_m["rank_ic"]) * 0.85
    against_m["model"] = against
    base_m = dict(base_m)
    base_m["model"] = baseline
    compare_payload = {"baseline": base_m, "against": against_m}

    console.print(
        f"Stub  {baseline} rank_ic={base_m['rank_ic']:.4f}  |  "
        f"{against} rank_ic={against_m['rank_ic']:.4f}"
    )
    console.print()
    console.print(default_banners(with_costs=with_costs).render())

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="compare",
                db_path=db_path,
                model=f"{baseline}_vs_{against}",
                scoreboard=ScoreboardMeta(costs=costs_label(with_costs=with_costs)),
                summary_md=(
                    f"# Compare stub · {ch.slug}\n\n"
                    f"`{baseline}` vs `{against}` — Phase 2 frame.\n\n"
                    "## Caveat\n\n"
                    "- Bukan saran trading / investasi.\n"
                    "- Angka stub, bukan hasil chapter real.\n"
                ),
                metrics=against_m,
                compare=compare_payload,
            ),
            artifacts_root=root,
        )
        console.print(f"\nArtifact:  {pack.path}")


@app.command("deepdive")
def deepdive_cmd(
    ctx: typer.Context,
    topic: str = typer.Argument(help="Topic slug"),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Jangan tulis artifact pack",
    ),
) -> None:
    """Opsional: kaitkan ke ai-saham + artifact."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    db_path: Path = ctx.obj["db"]
    console.print("[bold]Deep-dive · kaitkan ke ai-saham[/bold]")
    console.print(f"topic={ch.slug}")
    console.print(
        "[yellow]Deep-dive belum diisi "
        f"(opsional setelah chapter {ch.slug} live).[/yellow]"
    )

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        suggestions = (
            "# Suggestions for ai-saham (manual review)\n\n"
            f"Related: {ch.slug}\n\n"
            "## Evidence\n"
            "- (stub Phase 2 — isi setelah chapter live)\n\n"
            "## Possible knobs (do not apply blindly)\n"
            "- Validate on walk-forward before changing YAML\n\n"
            "## Not claimed\n"
            "- Live edge, auto-promote, or smart-money proof\n"
        )
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="deepdive",
                db_path=db_path,
                model=None,
                ai_saham_deepdive=True,
                summary_md=(
                    f"# Deep-dive stub · {ch.slug}\n\n"
                    "Human-applied suggestions only — tidak auto-edit ai-saham.\n"
                ),
                suggestions_md=suggestions,
            ),
            artifacts_root=root,
        )
        console.print(f"\nArtifact:  {pack.path}")

    mark(topic, "deepdive")


@app.command("glossary")
def glossary_cmd(
    term: Optional[str] = typer.Argument(None, help="Istilah (EN), opsional"),
) -> None:
    """Kamus bertahap (stub Phase 0)."""
    if term:
        console.print(f"[yellow]Kamus belum berisi entri untuk {term!r}.[/yellow]")
    else:
        console.print(
            "[yellow]Kamus bertahap masih kosong — "
            "akan terisi seiring chapter.[/yellow]"
        )


@app.command("doctor")
def doctor_cmd(ctx: typer.Context) -> None:
    """Cek DB path + kesiapan data MVP."""
    db_path: Path = ctx.obj["db"]
    report = run_doctor(db_path)
    console.print(format_doctor_report(report))
    if not report.mvp_hard_ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
