"""Shared deepdive stub copy for MVP chapters."""

from __future__ import annotations


def deepdive_stub(
    *,
    topic: str,
    related: str,
    bring_back: str,
) -> str:
    return (
        "Deep-dive · kaitkan ke ai-saham  [STUB MVP]\n"
        f"topic={topic}\n\n"
        f"Terkait: {related}\n"
        f"Yang bisa dibawa balik: {bring_back}\n"
        "Artifact: suggestions.md (human review only — jangan auto-edit YAML).\n"
        "Chapter utama sudah lengkap tanpa deep-dive ini.\n"
    )
