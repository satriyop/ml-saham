"""DiagnosticSpec registry (explain-only bags — not production PolicySpecs)."""

from ml_saham.challenge.diagnostics.registry import (
    list_diagnostic_ids,
    list_diagnostics,
    load_diagnostic,
    resolve_feature_key,
)

__all__ = [
    "list_diagnostic_ids",
    "list_diagnostics",
    "load_diagnostic",
    "resolve_feature_key",
]
