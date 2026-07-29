"""Load frozen policy snapshots (no ai-saham Python imports)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ml_saham.challenge.types import ComponentWeight, PolicySnapshot

# policy_id → packaged resource filename
_POLICY_FILES: dict[str, str] = {
    "screener.accum.score_weights": "accum_score_weights.v1.json",
}


def list_policy_ids() -> list[str]:
    return sorted(_POLICY_FILES)


@lru_cache(maxsize=16)
def load_policy(policy_id: str) -> PolicySnapshot:
    if policy_id not in _POLICY_FILES:
        # allow bare name without path prefix aliases
        aliases = {k.split(".")[-1]: k for k in _POLICY_FILES}
        # also full match after stripping version
        for k in _POLICY_FILES:
            if policy_id in (k, f"{k}.v1", k.replace("screener.", "")):
                policy_id = k
                break
        else:
            if policy_id in aliases:
                policy_id = aliases[policy_id]
            else:
                known = ", ".join(list_policy_ids())
                raise KeyError(f"Unknown policy_id {policy_id!r}. Known: {known}")

    name = _POLICY_FILES[policy_id]
    # Prefer filesystem next to this module (editable installs)
    here = Path(__file__).resolve().parent / name
    if here.is_file():
        data = json.loads(here.read_text(encoding="utf-8"))
    else:
        pkg = "ml_saham.challenge.policies"
        with resources.files(pkg).joinpath(name).open("r", encoding="utf-8") as fh:
            data = json.load(fh)

    comps = tuple(
        ComponentWeight(
            key=str(c["key"]),
            weight=float(c.get("weight") or 0.0),
            enabled=bool(c.get("enabled", True)),
            aliases=tuple(str(a) for a in c.get("aliases") or ()),
        )
        for c in data.get("components") or []
    )
    return PolicySnapshot(
        policy_id=str(data.get("policy_id") or policy_id),
        version=str(data.get("version") or "v1"),
        hash=str(data.get("hash") or ""),
        max_score=float(data.get("max_score") or 100.0),
        components=comps,
        source=str(data.get("source") or ""),
        source_ref=str(data.get("source_ref") or ""),
    )
