"""Explore output helpers (pager)."""

from __future__ import annotations

from rich.console import Console


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
