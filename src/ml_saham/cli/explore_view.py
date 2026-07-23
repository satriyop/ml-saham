"""Explore output helpers (pager / verbose)."""

from __future__ import annotations

from rich.console import Console

from ml_saham.chapters.registry import ChapterMeta


def explore_body(ch: ChapterMeta, *, verbose: bool = False) -> str:
    """Stub explore text until Phase 3 chapters fill real content."""
    lines = [
        f"Ch.{ch.number}  {ch.title}",
        f"topic={ch.slug}  phase={ch.phase}  data={ch.required_data}",
        "",
        "Masalah",
        "  Konten explore belum diisi (Phase 3).",
        "  Chapter ini mengajarkan masalah umum IDX dulu,",
        "  baru opsi ML — bukan textbook algoritma.",
        "",
        "Opsi pendekatan",
        "  1) Baseline aturan / heuristik sederhana",
        "  2) Model ML ringan sebagai pembanding",
        "  3) Evaluasi jujur (rank IC / skorboard vs IHSG)",
        "",
        "Caveat (baca sebelum demo)",
        "  • Data real dari DB pribadi; cek `ml-saham doctor` dulu",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya (default)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {ch.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Detail (--verbose)",
                "  • Progress: explore menandai E di `ml-saham chapters`",
                "  • Artifact: ditulis oleh `demo`/`compare` (bukan explore)",
                "  • Deep-dive opsional dan boleh dilewati",
                f"  • Required data tier: {ch.required_data}",
            ]
        )
    return "\n".join(lines)


def print_explore(
    console: Console,
    text: str,
    *,
    use_pager: bool = True,
) -> None:
    """Print explore text; page when terminal is interactive and not disabled."""
    if use_pager and console.is_terminal:
        with console.pager(styles=True):
            console.print(text)
    else:
        console.print(text)
