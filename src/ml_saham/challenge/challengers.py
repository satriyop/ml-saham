"""Shared challenger identity resolution for runner and promote reopen."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def resolve_named_gate_key(
    gate_key: str,
    components: Sequence[Any],
) -> str | None:
    """Return canonical component key if gate_key matches key or alias exactly.

    No strip/lower rewrite of the stored against_id key. Callers that normalize
    UX input must do so before sealing; promote reopen requires exact form.
    """
    if type(gate_key) is not str or not gate_key:
        return None
    for component in components:
        key = getattr(component, "key", None)
        if key == gate_key:
            return str(key)
        aliases = tuple(getattr(component, "aliases", ()) or ())
        if gate_key in aliases:
            return str(key)
    return None


def resolve_named_gate_key_normalized(
    gate_key: str,
    components: Sequence[Any],
) -> str | None:
    """UX/runner path: lowercase/underscore normalize then match component keys."""
    if type(gate_key) is not str or not gate_key:
        return None
    gkey = gate_key.strip().lower().replace("-", "_")
    for component in components:
        key = str(getattr(component, "key", "") or "")
        aliases = tuple(getattr(component, "aliases", ()) or ())
        if key.lower() == gkey or gkey in {a.lower() for a in aliases}:
            return key
    return None


def gate_keys_for_components(components: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(c.key) for c in components if getattr(c, "key", None))
