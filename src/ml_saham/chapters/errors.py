"""Chapter-facing errors (CLI should not dump raw tracebacks)."""

from __future__ import annotations


class ChapterError(Exception):
    """Base chapter failure with a learner-facing message."""


class ChapterDataError(ChapterError):
    """Missing/insufficient data — point user to `ml-saham doctor`."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        self.hint = hint or "Cek: ml-saham doctor"
        super().__init__(message)
