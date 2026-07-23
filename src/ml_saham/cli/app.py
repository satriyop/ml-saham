"""Typer CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ml_saham import __version__
from ml_saham.chapters import get as get_chapter
from ml_saham.chapters import mvp_chapters
from ml_saham.chapters.registry import all_chapters
from ml_saham.data.connection import resolve_db_path
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
) -> None:
    """Global options."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = resolve_db_path(db)


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
) -> None:
    """Jelaskan masalah umum + opsi + caveat (belum train)."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold]Ch.{ch.number}  {ch.title}[/bold]")
    console.print(f"topic={ch.slug}  phase={_phase_label(ch.phase)}  data={ch.required_data}")
    console.print(
        "\n[yellow]Konten explore belum diisi "
        f"(Phase 3 — chapter {ch.slug}).[/yellow]"
    )
    console.print(f"\nLanjut:  ml-saham demo {ch.slug}")
    mark(topic, "explore")


@app.command("demo")
def demo_cmd(
    topic: str = typer.Argument(help="Topic slug"),
) -> None:
    """Jalankan demo pada data real."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold]Demo Ch.{ch.number} {ch.slug}[/bold]")
    console.print(
        "[yellow]Demo belum diimplementasi "
        f"(Phase 3 — chapter {ch.slug}).[/yellow]"
    )
    console.print(
        "\n⚠ Skorboard: long-only vs IHSG · belum termasuk biaya"
        "\n⚠ Bukan saran trading / investasi"
    )
    mark(topic, "demo")


@app.command("compare")
def compare_cmd(
    topic: str = typer.Argument(help="Topic slug"),
    baseline: str = typer.Option(..., "--baseline", help="Baseline id"),
    against: str = typer.Option(..., "--against", help="Model pembanding"),
) -> None:
    """Bandingkan baseline vs model."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[yellow]Compare belum diimplementasi untuk {ch.slug} "
        f"({baseline} vs {against}).[/yellow]"
    )


@app.command("deepdive")
def deepdive_cmd(
    topic: str = typer.Argument(help="Topic slug"),
) -> None:
    """Opsional: kaitkan ke ai-saham + artifact."""
    try:
        ch = get_chapter(topic)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold]Deep-dive · kaitkan ke ai-saham[/bold]")
    console.print(f"topic={ch.slug}")
    console.print(
        "[yellow]Deep-dive belum diisi "
        f"(opsional setelah chapter {ch.slug} live).[/yellow]"
    )
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
    """Cek DB path + kesiapan data (cek tabel: Phase 1)."""
    db_path: Path = ctx.obj["db"]
    console.print(f"DB: {db_path}")
    if not db_path.is_file():
        console.print("[red]File DB tidak ditemukan.[/red]")
        console.print(
            "Set --db PATH atau env ML_SAHAM_DB, "
            "atau jalankan saham fetch market di ai-saham."
        )
        raise typer.Exit(code=1)
    console.print("[green]File DB ada.[/green]")
    console.print(
        "[yellow]Pemeriksaan tabel MVP data belum diimplementasi "
        "(Phase 1 — doctor checks).[/yellow]"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
