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
    write_artifact_pack,
)
from ml_saham.chapters import get as get_chapter
from ml_saham.chapters import mvp_chapters, v1_1_chapters
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.registry import all_chapters
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.explore_view import print_explore
from ml_saham.data.aisaham_read import connect
from ml_saham.data.connection import resolve_db_path
from ml_saham.data.doctor_checks import format_doctor_report, run_doctor
from ml_saham.data.universe import default_universe
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
        bits.append("E✓")
    if flags["demo"]:
        bits.append("D✓")
    if flags["deepdive"]:
        bits.append("DV✓")
    return " ".join(bits) if bits else "—"


def _fail_cmd(exc: BaseException, *, what: str = "Perintah") -> None:
    """Print learner-facing error without dumping a Python traceback."""
    console.print(f"[red]{what} gagal: {exc}[/red]")
    if isinstance(exc, ChapterDataError):
        console.print(f"[dim]{exc.hint}[/dim]")
    elif isinstance(exc, ChapterError):
        pass
    else:
        console.print("[dim]Cek: ml-saham doctor[/dim]")
    raise typer.Exit(code=1) from None


def _build_ctx(
    ctx: typer.Context,
    *,
    with_costs: bool = False,
    verbose: bool = False,
    as_of: str | None = None,
) -> ChapterContext:
    db_path: Path = ctx.obj["db"]
    universe: list[str] = []
    if db_path.is_file():
        with connect(db_path) as conn:
            universe = default_universe(conn)
    return ChapterContext(
        db_path=db_path,
        universe=universe,
        as_of=as_of,
        with_costs=with_costs,
        verbose=verbose,
    )


def _doctor_gate(db_path: Path, required_data: str) -> None:
    report = run_doctor(db_path)
    if report.tier_ok(required_data):
        return
    label = {"mvp": "MVP", "v1_1": "v1.1", "phase2": "phase-2"}.get(
        required_data, required_data
    )
    console.print(f"[red]Data {label} belum siap untuk demo/compare.[/red]")
    console.print(format_doctor_report(report))
    console.print("\nPerbaiki data, lalu: ml-saham doctor")
    raise typer.Exit(code=1)


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
        help="Tampilkan semua chapter (default: MVP + v1.1)",
    ),
) -> None:
    """Tampilkan jalur chapter dan progress."""
    table = Table(title="ml-saham chapters")
    table.add_column("#", justify="right")
    table.add_column("topic")
    table.add_column("phase")
    table.add_column("judul")
    table.add_column("progress", justify="center")

    if all_phases:
        rows = all_chapters()
    else:
        rows = (*mvp_chapters(), *v1_1_chapters())
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
            "\n[dim]MVP + v1.1. Progress: E✓=explore D✓=demo DV✓=deepdive. "
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

    if has_chapter_module(topic):
        mod = load_chapter(topic)
        text = mod.explore_text(verbose=verbose)
    else:
        text = (
            f"Ch.{ch.number}  {ch.title}\n"
            f"topic={ch.slug}  phase={_phase_label(ch.phase)}\n\n"
            "[Belum diimplementasi — di luar MVP Phase 3.]\n"
        )
    print_explore(console, text, use_pager=not no_pager)
    mark(topic, "explore")


@app.command("demo")
def demo_cmd(
    ctx: typer.Context,
    topic: str = typer.Argument(help="Topic slug"),
    with_costs: bool = typer.Option(
        False,
        "--with-costs",
        help="Terapkan haircut biaya sederhana pada metrik return",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Jangan tulis artifact pack",
    ),
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="Tanggal as_of (YYYY-MM-DD); default dipilih otomatis",
    ),
) -> None:
    """Jalankan demo pada data real."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not has_chapter_module(topic):
        console.print(
            f"[yellow]Demo belum diimplementasi untuk {ch.slug} "
            "(di luar MVP Phase 3).[/yellow]"
        )
        raise typer.Exit(code=1)

    _doctor_gate(ctx.obj["db"], ch.required_data)
    chapter_ctx = _build_ctx(ctx, with_costs=with_costs, as_of=as_of)
    mod = load_chapter(topic)
    try:
        result = mod.run_demo(chapter_ctx)
    except (ChapterDataError, ChapterError) as exc:
        _fail_cmd(exc, what="Demo")
    except Exception as exc:  # noqa: BLE001
        _fail_cmd(exc, what="Demo")

    console.print(f"[bold]{result.title}[/bold]")
    console.print(f"Data     db={chapter_ctx.db_path}")
    if chapter_ctx.universe:
        console.print(f"Universe n={len(chapter_ctx.universe)}")
    console.print("─" * 40)
    for line in result.lines:
        console.print(line)
    console.print("─" * 40)
    if result.scoreboard:
        console.print(default_banners(with_costs=with_costs).render())
    else:
        console.print("⚠ Bukan saran trading / investasi")
        console.print(
            "[dim](Ch. ini failure-lab accuracy — bukan skorboard vs IHSG)[/dim]"
        )

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="demo",
                db_path=chapter_ctx.db_path,
                model=result.model,
                as_of=chapter_ctx.as_of or result.metrics.get("as_of"),
                scoreboard=ScoreboardMeta(
                    type=(
                        "long_only_vs_ihsg"
                        if result.scoreboard
                        else "failure_lab"
                    ),
                    costs=costs_label(with_costs=with_costs),
                ),
                summary_md=result.summary_md,
                metrics=result.metrics,
                extra_files=result.extra_files,
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
        help="Terapkan haircut biaya sederhana pada metrik return",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Jangan tulis artifact pack",
    ),
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="Tanggal as_of (YYYY-MM-DD); default dipilih otomatis",
    ),
) -> None:
    """Bandingkan baseline vs model."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not has_chapter_module(topic):
        console.print(f"[yellow]Compare N/A untuk {ch.slug}.[/yellow]")
        raise typer.Exit(code=1)

    mod = load_chapter(topic)
    if not hasattr(mod, "run_compare"):
        console.print(f"[yellow]Compare belum tersedia untuk {ch.slug}.[/yellow]")
        raise typer.Exit(code=1)

    _doctor_gate(ctx.obj["db"], ch.required_data)
    chapter_ctx = _build_ctx(ctx, with_costs=with_costs, as_of=as_of)
    try:
        result = mod.run_compare(chapter_ctx, baseline=baseline, against=against)
    except (ChapterDataError, ChapterError) as exc:
        _fail_cmd(exc, what="Compare")
    except Exception as exc:  # noqa: BLE001
        _fail_cmd(exc, what="Compare")

    console.print(f"[bold]{result.title}[/bold]")
    for line in result.lines:
        console.print(line)
    if result.scoreboard:
        console.print()
        console.print(default_banners(with_costs=with_costs).render())

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="compare",
                db_path=chapter_ctx.db_path,
                model=result.model,
                as_of=result.compare.get("as_of") if result.compare else None,
                scoreboard=ScoreboardMeta(costs=costs_label(with_costs=with_costs)),
                summary_md=result.summary_md,
                metrics=result.metrics,
                compare=result.compare,
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

    console.print("[bold]Deep-dive · kaitkan ke ai-saham[/bold]")
    console.print(f"topic={ch.slug}")
    suggestions = None
    summary = (
        f"# Deep-dive · {ch.slug}\n\n"
        "Human-applied suggestions only — tidak auto-edit ai-saham.\n"
    )
    if has_chapter_module(topic):
        mod = load_chapter(topic)
        if hasattr(mod, "deepdive_text"):
            console.print(mod.deepdive_text())
        else:
            console.print(
                "[yellow]Deep-dive singkat (stub OK untuk MVP).[/yellow]\n"
                "Chapter utama sudah lengkap tanpa deep-dive."
            )
        suggestions = (
            "# Suggestions for ai-saham (manual review)\n\n"
            f"Related: {ch.slug}\n\n"
            "## Evidence\n"
            "- Lihat artifact demo/compare chapter ini.\n\n"
            "## Possible knobs (do not apply blindly)\n"
            "- Validate on walk-forward before changing YAML\n\n"
            "## Not claimed\n"
            "- Live edge, auto-promote, or smart-money proof\n"
        )
    else:
        console.print("[yellow]Deep-dive belum diisi (di luar MVP).[/yellow]")

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="deepdive",
                db_path=ctx.obj["db"],
                ai_saham_deepdive=True,
                summary_md=summary,
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
