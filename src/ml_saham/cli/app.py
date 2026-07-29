"""Typer CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ml_saham import __version__
from ml_saham.artifacts import (
    ArtifactWriteRequest,
    ScoreboardMeta,
    resolve_artifacts_root,
    write_artifact_pack,
)
from ml_saham.chapters import get as get_chapter
from ml_saham.chapters import mvp_chapters, phase2_chapters, v1_1_chapters
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.registry import all_chapters
from ml_saham.chapters.types import ChapterContext
from ml_saham.cli.explore_view import print_explore
from ml_saham.data.aisaham_read import connect
from ml_saham.data.connection import resolve_db_path
from ml_saham.data.doctor_checks import format_doctor_report, run_doctor
from ml_saham.data.universe import default_universe
from ml_saham.eval import costs_label, default_banners, open_session_banners
from ml_saham.progress import mark, topic_flags

app = typer.Typer(
    name="ml-saham",
    help="Kursus ML problem-centric untuk pasar IDX (personal learning).",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
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
        rows = (*mvp_chapters(), *v1_1_chapters(), *phase2_chapters())
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
            "\n[dim]MVP + v1.1 + phase-2. Opsional (Ch.20 rl-sandbox): ml-saham chapters --all. "
            "Progress: E✓ D✓ DV✓.[/dim]"
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
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Tulis hasil demo ke file JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Tulis hasil demo ke file Markdown factor card",
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
        if getattr(result, "scoreboard_kind", "long_only") == "open_session":
            console.print(open_session_banners(with_costs=with_costs).render())
        else:
            console.print(default_banners(with_costs=with_costs).render())
    else:
        console.print("⚠ Bukan saran trading / investasi")
        console.print(
            "[dim](Ch. ini failure-lab accuracy — bukan skorboard vs IHSG)[/dim]"
        )

    if not no_artifact:
        root = resolve_artifacts_root(ctx.obj.get("artifacts_dir"))
        sb_type = (
            "open_session"
            if getattr(result, "scoreboard_kind", "") == "open_session"
            else (
                "long_only_vs_ihsg"
                if result.scoreboard
                else "failure_lab"
            )
        )
        pack = write_artifact_pack(
            ArtifactWriteRequest(
                topic=ch.slug,
                chapter=ch.number,
                mode="demo",
                db_path=chapter_ctx.db_path,
                model=result.model,
                as_of=chapter_ctx.as_of or result.metrics.get("as_of"),
                scoreboard=ScoreboardMeta(
                    type=sb_type,
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

    if export_json:
        export_data = {
            "slug": ch.slug,
            "chapter": ch.number,
            "title": result.title,
            "model": result.model,
            "metrics": result.metrics,
            "scoreboard": result.scoreboard,
            "scoreboard_kind": getattr(result, "scoreboard_kind", "long_only"),
            "top_names": getattr(result, "top_names", []),
        }
        export_json.parent.mkdir(parents=True, exist_ok=True)
        export_json.write_text(json.dumps(export_data, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Saved JSON export to {export_json}[/green]")

    if export_md:
        md_lines = [
            f"# {result.title} (Ch.{ch.number} {ch.slug})",
            "",
            f"**Model**: `{result.model}`",
            f"**Database**: `{chapter_ctx.db_path}`",
            "",
            "## Metrics",
            "```json",
            json.dumps(result.metrics, indent=2, ensure_ascii=False),
            "```",
            "",
            "## Summary",
            result.summary_md or "",
        ]
        if getattr(result, "top_names", None):
            md_lines.extend(["", "## Top Picks", "```json", json.dumps(result.top_names, indent=2), "```"])
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text("\n".join(md_lines), encoding="utf-8")
        console.print(f"[green]Saved Markdown export to {export_md}[/green]")


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


@app.command("leaderboard")
def leaderboard_cmd(
    ctx: typer.Context,
    with_costs: bool = typer.Option(
        False,
        "--with-costs",
        help="Terapkan haircut biaya pada metrik return",
    ),
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="Tanggal as_of (YYYY-MM-DD); default dipilih otomatis",
    ),
    sort_by: str = typer.Option(
        "chapter",
        "--sort",
        help="Urutkan hasil berdasarkan: chapter, metric, slug",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Tulis hasil leaderboard ke file JSON",
    ),
) -> None:
    """Tampilkan papan peringkat metrik kuantitatif seluruh chapter ML."""
    chapters = all_chapters()
    chapter_ctx = _build_ctx(ctx, with_costs=with_costs, as_of=as_of)

    console.print("[bold cyan]=== QUANTITATIVE ML MODEL LEADERBOARD ===[/bold cyan]")
    console.print(f"Database: {chapter_ctx.db_path}\n")

    rows_data = []

    for ch in chapters:
        if not has_chapter_module(ch.slug):
            continue

        mod = load_chapter(ch.slug)
        try:
            res = mod.run_demo(chapter_ctx)
            metrics = res.metrics or {}

            primary_metric_name = "N/A"
            primary_metric_val = 0.0
            primary_metric_str = "—"

            for k, v in metrics.items():
                if k.startswith("rank_ic"):
                    primary_metric_name = k
                    primary_metric_val = float(v)
                    primary_metric_str = f"Rank IC: {primary_metric_val:+.3f}"
                    break
                elif "accuracy" in k:
                    primary_metric_name = k
                    primary_metric_val = float(v)
                    primary_metric_str = f"Accuracy: {primary_metric_val:.1%}"
                    break
                elif "precision" in k:
                    primary_metric_name = k
                    primary_metric_val = float(v)
                    primary_metric_str = f"Precision: {primary_metric_val:.1%}"
                    break

            top_names = getattr(res, "top_names", [])
            top_pick = (
                top_names[0]["ticker"]
                if top_names
                and isinstance(top_names[0], dict)
                and "ticker" in top_names[0]
                else "—"
            )

            rows_data.append(
                {
                    "number": ch.number,
                    "slug": ch.slug,
                    "title": ch.title,
                    "model": res.model,
                    "metric_name": primary_metric_name,
                    "metric_val": primary_metric_val,
                    "metric_str": primary_metric_str,
                    "top_pick": top_pick,
                }
            )
        except Exception:  # noqa: BLE001
            continue

    if sort_by == "metric":
        rows_data.sort(key=lambda r: abs(r["metric_val"]), reverse=True)
    elif sort_by == "slug":
        rows_data.sort(key=lambda r: r["slug"])
    else:
        rows_data.sort(key=lambda r: r["number"])

    table = Table(
        title="Papan Peringkat Strategy & Factor ML (30 Chapter)",
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Slug", style="bold green")
    table.add_column("Model ML", style="yellow")
    table.add_column("Primary Metric", justify="left")
    table.add_column("Top Pick", justify="center", style="bold white")

    for r in rows_data:
        table.add_row(
            str(r["number"]),
            r["slug"],
            r["model"],
            r["metric_str"],
            r["top_pick"],
        )

    console.print(table)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        export_json.write_text(
            json.dumps(rows_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        console.print(f"\n[green]Saved leaderboard JSON to {export_json}[/green]")


@app.command("challenge")
def challenge_cmd(
    ctx: typer.Context,
    target: str = typer.Argument(
        "all",
        help="Engine target: screener, engine, other, atau all",
    ),
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="Tanggal as_of (YYYY-MM-DD); default dipilih otomatis",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Tulis hasil challenge ke file JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Tulis hasil challenge ke file Markdown report",
    ),
    scenario: Optional[str] = typer.Option(
        None,
        "--scenario",
        help="Skenario spesifik (contoh: pre-open, accum)",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        help="Kategori engine (contoh: risk, signal)",
    ),
    eval_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Tipe evaluasi (contoh: gating, sizing)",
    ),
) -> None:
    """Audit sensitivitas & tantang faktor/parameter engine ai-saham."""
    from ml_saham.eval.challenge import (
        challenge_engine,
        challenge_other,
        challenge_screener,
        run_full_challenge,
    )

    db_path: Path = ctx.obj["db"]
    target_clean = target.lower().strip()
    chapter_ctx = _build_ctx(ctx, with_costs=False, as_of=as_of)
    chapter_ctx.scenario = scenario
    chapter_ctx.eval_type = eval_type

    console.print("[bold cyan]=== AI-SAHAM ENGINE CHALLENGE & PARAMETER AUDIT ===[/bold cyan]")
    console.print(f"Database: {db_path}\n")

    results: dict = {}

    if target_clean in ("screener", "screen"):
        results = {"screener": challenge_screener(chapter_ctx, scenario)}
    elif target_clean == "engine":
        results = {"engine": challenge_engine(chapter_ctx, category, eval_type)}
    elif target_clean in ("other", "other_aspects"):
        results = {"other_aspects": challenge_other(chapter_ctx)}
    else:
        results = run_full_challenge(chapter_ctx)

    for category, res in results.items():
        console.print(f"\n[bold yellow]=== Category: {category.upper()} ===[/bold yellow]")
        for k, v in res.items():
            if "error" in v:
                console.print(f"[bold red]❌ {k}[/bold red]")
                console.print(f"  [red]Error: {v['error']}[/red]")
            else:
                title = v.get("title", k)
                console.print(f"\n[bold green]✅ {title}[/bold green] ([cyan]{k}[/cyan])")
                if "model" in v:
                    console.print(f"   [dim]Model:[/dim] {v['model']}")
                
                # Format metrics side by side or simply
                sota = v.get("sota_metrics", {})
                baseline = v.get("baseline_metrics", {})
                if sota or baseline:
                    console.print("   [dim]Metrics:[/dim]")
                    if sota:
                        console.print(f"     [bold blue]SOTA:[/bold blue] {sota}")
                    if baseline:
                        console.print(f"     [bold blue]Baseline:[/bold blue] {baseline}")
                
                summary = v.get("summary")
                if summary:
                    console.print(Panel(Markdown(summary), title="Penjelasan Audit", border_style="dim"))
        console.print("─" * 60)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        export_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"\n[green]Saved challenge audit JSON to {export_json}[/green]")

    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        md_text = f"# ai-saham Engine Challenge Report\n\n```json\n{json.dumps(results, indent=2)}\n```\n"
        export_md.write_text(md_text, encoding="utf-8")
        console.print(f"[green]Saved challenge audit Markdown report to {export_md}[/green]")


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
