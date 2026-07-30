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
    help="Challenge lab for ai-saham (+ learn curriculum onboarding).",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
challenge_app = typer.Typer(
    name="challenge",
    help="ADR-002 policy challenges (run/list/engine/factor/diagnostic/health/champion).",
    no_args_is_help=True,
)
diagnostic_app = typer.Typer(
    name="diagnostic",
    help=(
        "Diagnostic validity (explain-only bags): KEEP_DISPLAY / DEMOTE_DISPLAY / "
        "PROMOTE_CANDIDATE — never Action authority."
    ),
    no_args_is_help=True,
)
learn_app = typer.Typer(
    name="learn",
    help="Curriculum onboarding (list/explore/demo/compare) — not promotion authority.",
    no_args_is_help=True,
)
app.add_typer(challenge_app, name="challenge")
challenge_app.add_typer(diagnostic_app, name="diagnostic")
app.add_typer(learn_app, name="learn")
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


@learn_app.command("list")
@learn_app.command("chapters")
def learn_list_cmd(
    all_phases: bool = typer.Option(
        False,
        "--all",
        help="Tampilkan semua chapter (default: MVP + v1.1)",
    ),
) -> None:
    """Tampilkan jalur chapter dan progress."""
    table = Table(title="ml-saham learn list")
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
            "\n[dim]MVP + v1.1 + phase-2. Opsional (Ch.20 rl-sandbox): ml-saham learn list --all. "
            "Progress: E✓ D✓.[/dim]"
        )


@learn_app.command("status")
def learn_status_cmd(ctx: typer.Context) -> None:
    """Ringkas DB + progress MVP."""
    db_path: Path = ctx.obj["db"]
    console.print(f"DB: {db_path}")
    console.print(f"Ada file: {'ya' if db_path.is_file() else 'tidak'}")
    console.print(f"Versi: {__version__}")
    console.print("\nProgress MVP:")
    for ch in mvp_chapters():
        console.print(f"  Ch.{ch.number} {ch.slug}: {_progress_cell(ch.slug)}")


@learn_app.command("explore")
def learn_explore_cmd(
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


@learn_app.command("demo")
def learn_demo_cmd(
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


@learn_app.command("compare")
def learn_compare_cmd(
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


@learn_app.command("leaderboard")
def learn_leaderboard_cmd(
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


@challenge_app.command("list")
def challenge_list_cmd() -> None:
    """List ADR-002 policy challenges."""
    from ml_saham.challenge import list_policies

    rows = list_policies()
    table = Table(title="Policy challenges (ADR-002)")
    table.add_column("policy_id")
    table.add_column("version")
    table.add_column("hash")
    table.add_column("protocol")
    for r in rows:
        table.add_row(r["policy_id"], r["version"], r["hash"], r["protocol"])
    console.print(table)
    console.print(
        "[dim]Run: ml-saham challenge run screener.accum.score_weights "
        "--against ridge_reweight[/dim]"
    )
    console.print(
        "[dim]Run: ml-saham challenge run screener.pre_open.iev_rank "
        "--against equal_sleeves[/dim]"
    )
    console.print(
        "[dim]Run: ml-saham challenge run screener.pre_open.directional_score "
        "--against equal_sleeves[/dim]"
    )
    console.print(
        "[dim]Factor: ml-saham challenge factor screener.accum.score_weights "
        "--factor consistency[/dim]"
    )
    console.print(
        "[dim]Diagnostic: ml-saham challenge diagnostic list | "
        "run mce.screen_display --all[/dim]"
    )


@diagnostic_app.command("list")
def challenge_diagnostic_list_cmd() -> None:
    """List registered DiagnosticSpecs (explain-only bags)."""
    from ml_saham.challenge import list_diagnostic_catalog

    rows = list_diagnostic_catalog()
    table = Table(title="Diagnostic bags (ADR-057 — not Action authority)")
    table.add_column("diagnostic_id")
    table.add_column("version")
    table.add_column("hash")
    table.add_column("engine")
    table.add_column("scenario")
    table.add_column("protocol")
    table.add_column("n_feat", justify="right")
    for r in rows:
        table.add_row(
            str(r["diagnostic_id"]),
            str(r["version"]),
            str(r["hash"]),
            str(r["engine"]),
            str(r["scenario"]),
            str(r["protocol"]),
            str(r["n_features"]),
        )
    console.print(table)
    console.print(
        "[dim]Run: ml-saham challenge diagnostic run mce.screen_display --all[/dim]"
    )
    console.print(
        "[dim]Run: ml-saham challenge diagnostic run sector.peer_context "
        "--feature sector_context_score[/dim]"
    )
    console.print(
        "[yellow]Verdicts are display/promote-candidate only — never set Action.[/yellow]"
    )


@diagnostic_app.command("run")
def challenge_diagnostic_run_cmd(
    ctx: typer.Context,
    diagnostic_id: str = typer.Argument(
        ...,
        help="Diagnostic id (see: ml-saham challenge diagnostic list)",
    ),
    feature: Optional[str] = typer.Option(
        None,
        "--feature",
        "-f",
        help="Bag field key or alias (e.g. regime_score, vix)",
    ),
    all_features: bool = typer.Option(
        False,
        "--all",
        help="Run validity for every enabled feature in the bag",
    ),
    list_features: bool = typer.Option(
        False,
        "--list-features",
        help="List enabled features for the diagnostic and exit",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write full result JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write summary markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack under artifacts/challenge/diagnostic/",
    ),
) -> None:
    """Calibrate explain-only bag: KEEP_DISPLAY / DEMOTE / DROP / PROMOTE_CANDIDATE."""
    from ml_saham.challenge import (
        list_enabled_diagnostic_features,
        run_diagnostic_challenge,
        run_diagnostic_challenge_batch,
    )

    if list_features:
        try:
            rows = list_enabled_diagnostic_features(diagnostic_id)
        except KeyError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from None
        table = Table(title=f"Enabled features — {diagnostic_id}")
        table.add_column("key")
        table.add_column("aliases")
        table.add_column("note")
        for r in rows:
            table.add_row(
                str(r["key"]),
                ", ".join(str(a) for a in (r.get("aliases") or [])),
                str(r.get("note") or ""),
            )
        console.print(table)
        raise typer.Exit(code=0)

    if all_features and feature:
        console.print("[red]Use either --all or --feature, not both.[/red]")
        raise typer.Exit(code=2)
    if not all_features and not feature:
        console.print(
            "[red]Require --feature KEY or --all (or use --list-features).[/red]"
        )
        raise typer.Exit(code=2)

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")

    if all_features:
        batch = run_diagnostic_challenge_batch(
            db_path,
            diagnostic_id,
            write_artifact=not no_artifact,
            artifacts_dir=Path(arts) if arts else None,
        )
        for line in batch.lines:
            console.print(line)
        if export_json:
            export_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "diagnostic_id": batch.diagnostic_id,
                "protocol_id": batch.protocol_id,
                "diagnostic_hash": batch.diagnostic_hash,
                "n_rows": batch.n_rows,
                "primary_horizon": batch.primary_horizon,
                "blocked": batch.blocked.value if batch.blocked else None,
                "features": [
                    {
                        "feature": r.feature,
                        "verdict": r.verdict.value,
                        "coverage": r.coverage,
                        "mean_univariate_ic": r.mean_univariate_ic,
                        "mean_residual_ic": r.mean_residual_ic,
                        "mean_redundancy": r.mean_redundancy,
                        "notes": r.notes[-3:],
                    }
                    for r in batch.results
                ],
                "artifact_dir": str(batch.artifact_dir) if batch.artifact_dir else None,
                "banner": "ADR-057: not Action authority",
            }
            export_json.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            console.print(f"\n[green]Saved JSON to {export_json}[/green]")
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(batch.summary_md, encoding="utf-8")
            console.print(f"[green]Saved Markdown to {export_md}[/green]")
        raise typer.Exit(code=batch.exit_code())

    result = run_diagnostic_challenge(
        db_path,
        diagnostic_id,
        feature=feature or "",
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)
    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "verdict": result.verdict.value,
            "diagnostic_id": result.diagnostic_id,
            "protocol_id": result.protocol_id,
            "diagnostic_hash": result.diagnostic_hash,
            "feature": result.feature,
            "n_rows": result.n_rows,
            "primary_horizon": result.primary_horizon,
            "coverage": result.coverage,
            "mean_univariate_ic": result.mean_univariate_ic,
            "mean_residual_ic": result.mean_residual_ic,
            "mean_redundancy": result.mean_redundancy,
            "horizon_metrics": result.horizon_metrics,
            "fold_metrics": result.fold_metrics,
            "notes": result.notes,
            "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
            "banner": "ADR-057: not Action authority",
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(result.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")
    raise typer.Exit(code=result.exit_code())


@diagnostic_app.command("health")
def challenge_diagnostic_health_cmd(
    ctx: typer.Context,
    scenario: str = typer.Option(
        "accum",
        "--scenario",
        help="Scenario filter for registered diagnostics (default: accum)",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write full result JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write summary markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack",
    ),
) -> None:
    """Control-tower style rollup of all diagnostic bags for a scenario."""
    from ml_saham.challenge import run_diagnostic_health

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")
    batch = run_diagnostic_health(
        db_path,
        scenario=scenario,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in batch.lines:
        console.print(line)
    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "diagnostic_id": batch.diagnostic_id,
            "protocol_id": batch.protocol_id,
            "n_rows": batch.n_rows,
            "blocked": batch.blocked.value if batch.blocked else None,
            "features": [
                {
                    "feature": r.feature,
                    "diagnostic_id": r.diagnostic_id,
                    "verdict": r.verdict.value,
                    "coverage": r.coverage,
                    "mean_residual_ic": r.mean_residual_ic,
                    "mean_univariate_ic": r.mean_univariate_ic,
                }
                for r in batch.results
            ],
            "artifact_dir": str(batch.artifact_dir) if batch.artifact_dir else None,
            "banner": "ADR-057: not Action authority",
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(batch.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")
    raise typer.Exit(code=batch.exit_code())


@challenge_app.command("factor")
def challenge_factor_cmd(
    ctx: typer.Context,
    policy_id: str = typer.Argument(
        "screener.accum.score_weights",
        help="Policy id (see: ml-saham challenge list)",
    ),
    factor: Optional[str] = typer.Option(
        None,
        "--factor",
        "-f",
        help="Enabled sleeve key or alias (e.g. consistency, cons, streak)",
    ),
    all_factors: bool = typer.Option(
        False,
        "--all",
        help="Run validity for every enabled sleeve (summary table)",
    ),
    list_factors: bool = typer.Option(
        False,
        "--list-factors",
        help="List enabled factors for the policy and exit",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write full result JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write summary markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack under artifacts/challenge/factor/",
    ),
) -> None:
    """Factor validity: univariate IC + drop ablation → KEEP/DEMOTE/DROP_CANDIDATE."""
    from ml_saham.challenge import (
        list_enabled_factors,
        run_factor_challenge,
        run_factor_challenge_batch,
    )

    if list_factors:
        try:
            rows = list_enabled_factors(policy_id)
        except KeyError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from None
        table = Table(title=f"Enabled factors — {policy_id}")
        table.add_column("key")
        table.add_column("weight")
        table.add_column("aliases")
        for r in rows:
            table.add_row(
                str(r["key"]),
                str(r["weight"]),
                ", ".join(str(a) for a in (r.get("aliases") or [])),
            )
        console.print(table)
        raise typer.Exit(code=0)

    if all_factors and factor:
        console.print("[red]Use either --all or --factor, not both.[/red]")
        raise typer.Exit(code=2)
    if not all_factors and not factor:
        console.print(
            "[red]Require --factor KEY or --all (or use --list-factors).[/red]"
        )
        raise typer.Exit(code=2)

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")

    if all_factors:
        batch = run_factor_challenge_batch(
            db_path,
            policy_id,
            write_artifact=not no_artifact,
            artifacts_dir=Path(arts) if arts else None,
        )
        for line in batch.lines:
            console.print(line)
        if export_json:
            export_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "policy_id": batch.policy_id,
                "protocol_id": batch.protocol_id,
                "policy_hash": batch.policy_hash,
                "n_rows": batch.n_rows,
                "primary_horizon": batch.primary_horizon,
                "blocked": batch.blocked.value if batch.blocked else None,
                "factors": [
                    {
                        "factor": r.factor,
                        "verdict": r.verdict.value,
                        "mean_delta_ic": r.mean_delta_ic,
                        "mean_univariate_ic": r.mean_univariate_ic,
                        "fold_agree_positive_delta": r.fold_agree_positive_delta,
                        "notes": r.notes[-3:],
                    }
                    for r in batch.results
                ],
                "artifact_dir": str(batch.artifact_dir) if batch.artifact_dir else None,
            }
            export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            console.print(f"\n[green]Saved JSON to {export_json}[/green]")
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(batch.summary_md, encoding="utf-8")
            console.print(f"[green]Saved Markdown to {export_md}[/green]")
        raise typer.Exit(code=batch.exit_code())

    result = run_factor_challenge(
        db_path,
        policy_id,
        factor=factor or "",
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "verdict": result.verdict.value,
            "policy_id": result.policy_id,
            "protocol_id": result.protocol_id,
            "policy_hash": result.policy_hash,
            "factor": result.factor,
            "n_rows": result.n_rows,
            "primary_horizon": result.primary_horizon,
            "mean_delta_ic": result.mean_delta_ic,
            "mean_univariate_ic": result.mean_univariate_ic,
            "fold_agree_positive_delta": result.fold_agree_positive_delta,
            "horizon_metrics": result.horizon_metrics,
            "fold_metrics": result.fold_metrics,
            "notes": result.notes,
            "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(result.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")

    raise typer.Exit(code=result.exit_code())


@challenge_app.command("health")
def challenge_health_cmd(
    ctx: typer.Context,
    scenario: Optional[str] = typer.Option(
        None,
        "--scenario",
        help="ai-saham scenario filter: accum | pre-open (omit = all)",
    ),
    with_champion: bool = typer.Option(
        False,
        "--with-champion",
        help="Also run champion lgbm_reweight on accum policy",
    ),
    with_factors: bool = typer.Option(
        False,
        "--with-factors",
        help="Also run factor --all on accum policy (always accum, not scenario-filtered)",
    ),
    with_diagnostics: bool = typer.Option(
        False,
        "--with-diagnostics",
        help=(
            "Also run diagnostic display-bag validity (KEEP_DISPLAY / PROMOTE_CANDIDATE); "
            "never mixed into sleeve KEEP/DEMOTE"
        ),
    ),
    champion_model: str = typer.Option(
        "lgbm_reweight",
        "--champion-model",
        help="Champion model when --with-champion (lgbm_reweight | elastic_net_reweight)",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Print summary only; skip artifacts/challenge/health pack",
    ),
) -> None:
    """Control tower: engine rollup ± champion ± factors ± diagnostics → English pack."""
    from ml_saham.challenge.health import build_health_report

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")
    result = build_health_report(
        db_path,
        scenario=scenario,
        with_champion=with_champion,
        with_factors=with_factors,
        with_diagnostics=with_diagnostics,
        champion_model=champion_model,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)
    if result.artifact_dir:
        console.print(f"\n[green]Health pack: {result.artifact_dir}[/green]")
    raise typer.Exit(code=result.exit_code())


@challenge_app.command("promote-packet")
def challenge_promote_packet_cmd(
    ctx: typer.Context,
    from_json: Optional[Path] = typer.Option(
        None,
        "--from-json",
        help="Export JSON from challenge run / champion",
    ),
    from_artifact: Optional[Path] = typer.Option(
        None,
        "--from-artifact",
        help="Challenge artifact directory (manifest.json + metrics.json)",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Print only; skip writing promote pack",
    ),
) -> None:
    """Build human promote/reject checklist from a result. Never applies to ai-saham."""
    from ml_saham.challenge.promote import build_promote_packet

    arts = ctx.obj.get("artifacts_dir")
    result = build_promote_packet(
        from_json=from_json,
        from_artifact=from_artifact,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)
    if result.error:
        console.print(f"[red]{result.error}[/red]")
    elif result.summary_md and no_artifact:
        console.print(result.summary_md[:2000])
    if result.artifact_dir:
        console.print(f"\n[green]Promote pack: {result.artifact_dir}[/green]")
    raise typer.Exit(code=result.exit_code())


@challenge_app.command("champion")
def challenge_champion_cmd(
    ctx: typer.Context,
    policy_id: str = typer.Argument(
        "screener.accum.score_weights",
        help="Policy id (champion M1: accum score_weights)",
    ),
    model: str = typer.Option(
        "lgbm_reweight",
        "--model",
        "-m",
        help="Champion model: lgbm_reweight | elastic_net_reweight",
    ),
    baseline: str = typer.Option(
        "production",
        "--baseline",
        help="Baseline id (v1: production only)",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write full result JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write summary markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack under artifacts/challenge/",
    ),
) -> None:
    """Champion track: learned score rule vs production (not factor/weight tune).

    Answers: is there a better scoring rule than production under the same
    protocol? Production stays baseline. Never auto-promotes ai-saham.
    For factor/weight tuning use: challenge run / challenge factor.
    """
    from ml_saham.challenge import run_policy_challenge
    from ml_saham.challenge.champion import is_champion_against, normalize_champion_id

    against = normalize_champion_id(model)
    if not is_champion_against(against):
        console.print(
            f"[red]Unknown champion model {model!r}. "
            "Use lgbm_reweight | elastic_net_reweight[/red]"
        )
        raise typer.Exit(code=2)

    console.print(
        "[bold cyan]CHAMPION TRACK[/bold cyan] — beat production with a learned "
        "score rule (not sleeve tuning). No auto-promote.\n"
    )

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")
    result = run_policy_challenge(
        db_path,
        policy_id,
        against=against,
        baseline=baseline,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "champion",
            "status": result.status.value,
            "policy_id": result.policy_id,
            "protocol_id": result.protocol_id,
            "policy_hash": result.policy_hash,
            "baseline_id": result.baseline_id,
            "against_id": result.against_id,
            "n_rows": result.n_rows,
            "primary_horizon": result.primary_horizon,
            "primary_ic_baseline": result.primary_ic_baseline,
            "primary_ic_against": result.primary_ic_against,
            "horizon_metrics": result.horizon_metrics,
            "fold_metrics": result.fold_metrics,
            "weights": result.weights,
            "notes": result.notes,
            "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(result.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")

    raise typer.Exit(code=result.exit_code())


@challenge_app.command("run")
def challenge_run_cmd(
    ctx: typer.Context,
    policy_id: str = typer.Argument(
        "screener.accum.score_weights",
        help="Policy id (see: ml-saham challenge list)",
    ),
    against: str = typer.Option(
        "ridge_reweight",
        "--against",
        help=(
            "Tune: equal_sleeves | ridge_reweight. "
            "Champion (also via `challenge champion`): lgbm_reweight | elastic_net_reweight"
        ),
    ),
    baseline: str = typer.Option(
        "production",
        "--baseline",
        help="Baseline id (v1: production only)",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write full result JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write summary markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack under artifacts/challenge/",
    ),
) -> None:
    """Run ADR-002 policy tournament (English report)."""
    from ml_saham.challenge import run_policy_challenge

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")
    result = run_policy_challenge(
        db_path,
        policy_id,
        against=against,
        baseline=baseline,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": result.status.value,
            "policy_id": result.policy_id,
            "protocol_id": result.protocol_id,
            "policy_hash": result.policy_hash,
            "baseline_id": result.baseline_id,
            "against_id": result.against_id,
            "n_rows": result.n_rows,
            "primary_horizon": result.primary_horizon,
            "primary_ic_baseline": result.primary_ic_baseline,
            "primary_ic_against": result.primary_ic_against,
            "horizon_metrics": result.horizon_metrics,
            "fold_metrics": result.fold_metrics,
            "weights": result.weights,
            "notes": result.notes,
            "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(result.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")

    raise typer.Exit(code=result.exit_code())


@challenge_app.command("engine")
def challenge_engine_cmd(
    ctx: typer.Context,
    name: str = typer.Argument(
        "list",
        help="Engine id (e.g. screener) or 'list' to show engines",
    ),
    scenario: Optional[str] = typer.Option(
        None,
        "--scenario",
        help="ai-saham scenario filter: accum | pre-open (omit = all)",
    ),
    against: str = typer.Option(
        "equal_sleeves",
        "--against",
        help="Shared challenger for all policies (default: equal_sleeves)",
    ),
    baseline: str = typer.Option(
        "production",
        "--baseline",
        help="Baseline id (v1: production only)",
    ),
    export_json: Optional[Path] = typer.Option(
        None,
        "--export-json",
        help="Write engine rollup JSON",
    ),
    export_md: Optional[Path] = typer.Option(
        None,
        "--export-md",
        help="Write engine rollup markdown",
    ),
    no_artifact: bool = typer.Option(
        False,
        "--no-artifact",
        help="Skip artifact pack under artifacts/challenge/engine/",
    ),
) -> None:
    """ADR-002 engine portfolio: PolicySpecs rollup."""
    from ml_saham.challenge.engines import list_engines, run_engine_portfolio

    name_clean = name.strip().lower()
    if name_clean in ("list", "ls", ""):
        table = Table(title="Engines (ADR-002 PolicySpec portfolios)")
        table.add_column("engine_id")
        table.add_column("scenarios")
        table.add_column("n_policies")
        for e in list_engines():
            table.add_row(
                e["engine_id"],
                ", ".join(e["scenarios"]),
                str(e["n_policies"]),
            )
        console.print(table)
        console.print(
            "[dim]Run: ml-saham challenge engine screener "
            "[--scenario accum|pre-open] --against equal_sleeves[/dim]"
        )
        raise typer.Exit(code=0)

    db_path: Path = ctx.obj["db"]
    arts = ctx.obj.get("artifacts_dir")
    result = run_engine_portfolio(
        db_path,
        name_clean,
        scenario=scenario,
        against=against,
        baseline=baseline,
        write_artifact=not no_artifact,
        artifacts_dir=Path(arts) if arts else None,
    )
    for line in result.lines:
        console.print(line)

    if export_json:
        export_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "engine_id": result.engine_id,
            "scenario_filter": result.scenario_filter,
            "against_id": result.against_id,
            "baseline_id": result.baseline_id,
            "counts": result.counts,
            "notes": result.notes,
            "resolve_error": result.resolve_error,
            "rows": [
                {
                    "scenario": r.scenario,
                    "policy_id": r.policy_id,
                    "protocol_id": r.protocol_id,
                    "status": r.status,
                    "n_rows": r.n_rows,
                    "primary_horizon": r.primary_horizon,
                    "primary_ic_baseline": r.primary_ic_baseline,
                    "primary_ic_against": r.primary_ic_against,
                    "notes": r.notes[-5:],
                    "error": r.error,
                }
                for r in result.rows
            ],
            "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
        }
        export_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        console.print(f"\n[green]Saved JSON to {export_json}[/green]")
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(result.summary_md, encoding="utf-8")
        console.print(f"[green]Saved Markdown to {export_md}[/green]")

    raise typer.Exit(code=result.exit_code())


@learn_app.command("glossary")
def learn_glossary_cmd(
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
def doctor_cmd(
    ctx: typer.Context,
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Include data-integrity tier (observations, date overlap, PIT depth)",
    ),
) -> None:
    """Check DB path + data tiers (+ optional integrity)."""
    db_path: Path = ctx.obj["db"]
    report = run_doctor(db_path, deep=deep)
    console.print(format_doctor_report(report))
    if not report.mvp_hard_ok:
        raise typer.Exit(code=1)


@app.command("vet")
def vet_cmd(
    ctx: typer.Context,
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="as_of date (YYYY-MM-DD); optional",
    ),
) -> None:
    """English data-integrity audit (challenge factor) before engine challenge."""
    from ml_saham.chapters.loader import load_chapter

    db_path: Path = ctx.obj["db"]
    chapter_ctx = _build_ctx(ctx, with_costs=False, as_of=as_of)
    console.print("[bold cyan]=== DATA PLANE VET (ai-saham) ===[/bold cyan]")
    console.print(f"Database: {db_path}\n")

    # Always show deep doctor integrity section
    report = run_doctor(db_path, deep=True)
    console.print(format_doctor_report(report))
    console.print()

    mod = load_chapter("data-integrity")
    result = mod.run_compare(chapter_ctx)
    console.print(f"[bold]{result.title}[/bold]")
    for line in result.lines:
        console.print(line)
    if getattr(result, "winner", None):
        console.print(f"\n[dim]Winner:[/dim] {result.winner}")

    # Soft gate: exit 1 only if MVP hard fails; integrity thin → warning via report
    if not report.mvp_hard_ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
