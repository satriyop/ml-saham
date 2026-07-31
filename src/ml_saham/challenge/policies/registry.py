"""Load ML-owned challenge adapters and legacy pre-open local specs."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ml_saham.challenge.types import (
    ChallengeAdapterComponent,
    ChallengeExecutionPolicy,
    ChallengePolicyAdapter,
    ComponentWeight,
)

# policy_id → packaged resource filename
_POLICY_FILES: dict[str, str] = {
    "screener.accum.score_weights": "accum_score_weights.fixture.v1.json",
    "screener.pre_open.iev_rank": "pre_open_iev_rank.v1.json",
    "screener.pre_open.directional_score": "pre_open_directional_score.v1.json",
    "signal.accum.raw_score": "signal_accum_raw_score.fixture.v1.json",
    "signal.accum.flags": "signal_accum_flags.fixture.v1.json",
    "signal.accum.classification": "signal_accum_classification.fixture.v1.json",
    "signal.accum.evidence_group_weights": "signal_accum_evidence_group_weights.fixture.v1.json",
    "risk.accum.hard_gates": "risk_accum_hard_gates.fixture.v1.json",
}

_ADAPTER_FILES: dict[str, str] = {
    "screener.accum.score_weights": "accum_score_weights.adapter.v1.json",
    "signal.accum.evidence_group_weights": (
        "signal_accum_evidence_group_weights.adapter.v1.json"
    ),
    "signal.accum.flags": "signal_accum_flags.adapter.v1.json",
    "signal.accum.classification": "signal_accum_classification.adapter.v1.json",
    "risk.accum.hard_gates": "risk_accum_hard_gates.adapter.v1.json",
    "signal.accum.raw_score": "signal_accum_raw_score.adapter.v1.json",
    "screener.accum.hard_filters": "screener_accum_hard_filters.adapter.v1.json",
}


def list_policy_ids() -> list[str]:
    return sorted(set(_POLICY_FILES) | set(_ADAPTER_FILES))


def _resolve_policy_id(policy_id: str) -> str:
    known_files = {**_POLICY_FILES, **_ADAPTER_FILES}
    if policy_id in known_files:
        return policy_id
    aliases = {k.split(".")[-1]: k for k in known_files}
    for k in known_files:
        if policy_id in (k, f"{k}.v1", k.replace("screener.", "")):
            return k
    if policy_id in aliases:
        return aliases[policy_id]
    # dotted tail match e.g. pre_open.iev_rank
    for k in known_files:
        if policy_id == k.removeprefix("screener.") or k.endswith(policy_id):
            return k
    known = ", ".join(list_policy_ids())
    raise KeyError(f"Unknown policy_id {policy_id!r}. Known: {known}")


def _load_json(name: str) -> dict:
    """Load an immutable packaged challenge spec."""
    here = Path(__file__).resolve().parent / name
    if here.is_file():
        return json.loads(here.read_text(encoding="utf-8"))
    pkg = "ml_saham.challenge.policies"
    with resources.files(pkg).joinpath(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_policy_data(policy_id: str) -> tuple[str, dict]:
    policy_id = _resolve_policy_id(policy_id)
    name = _POLICY_FILES.get(policy_id)
    if name is None:
        raise KeyError(f"No local execution fixture for {policy_id!r}")
    return policy_id, _load_json(name)


def _components(data: dict) -> tuple[ComponentWeight, ...]:
    return tuple(
        ComponentWeight(
            key=str(c["key"]),
            weight=float(c.get("weight") or 0.0),
            enabled=bool(c.get("enabled", True)),
            aliases=tuple(str(a) for a in c.get("aliases") or ()),
        )
        for c in data.get("components") or []
    )


@lru_cache(maxsize=16)
def load_policy_adapter(policy_id: str) -> ChallengePolicyAdapter:
    """Load a clean ML-owned adapter containing no production material."""

    policy_id = _resolve_policy_id(policy_id)
    name = _ADAPTER_FILES.get(policy_id)
    if name is None:
        raise KeyError(f"No verified accumulation adapter for {policy_id!r}")
    data = _load_json(name)
    if data.get("supported_policy_id") != policy_id:
        raise KeyError(f"Adapter policy identity mismatch for {policy_id!r}")
    return ChallengePolicyAdapter(
        adapter_id=str(data["adapter_id"]),
        adapter_version=str(data["adapter_version"]),
        supported_policy_id=policy_id,
        supported_snapshot_contract=str(data["supported_snapshot_contract"]),
        supported_semantic_engine_contract_ids=tuple(
            str(value) for value in data["supported_semantic_engine_contract_ids"]
        ),
        protocol_id=str(data["protocol_id"]),
        panel_kind=str(data["panel_kind"]),
        score_kind=str(data["score_kind"]),
        components=tuple(
            ChallengeAdapterComponent(
                key=str(component["key"]),
                aliases=tuple(str(alias) for alias in component.get("aliases") or ()),
            )
            for component in data.get("components") or ()
        ),
        supported_challengers=tuple(
            str(value) for value in data["supported_challengers"]
        ),
        conformance_id=str(data.get("conformance_id") or ""),
    )


@lru_cache(maxsize=16)
def load_policy(policy_id: str) -> ChallengeExecutionPolicy:
    """Load a local adapter fixture or non-accum legacy execution spec.

    Accumulation challenge preparation must call ``load_policy_adapter`` and
    compose it with a verified upstream snapshot. Accum rows returned here have
    no production identity and may only support isolated extractor/scorer tests.
    """

    policy_id, data = _load_policy_data(policy_id)
    is_accum_adapter_fixture = policy_id in _ADAPTER_FILES

    return ChallengeExecutionPolicy(
        policy_id=str(data.get("policy_id") or policy_id),
        version=str(data.get("version") or "v1"),
        hash="" if is_accum_adapter_fixture else str(data.get("hash") or ""),
        max_score=float(data.get("max_score") or 100.0),
        components=_components(data),
        source=(
            "ML adapter fixture; not production authority"
            if is_accum_adapter_fixture
            else str(data.get("source") or "")
        ),
        source_ref=""
        if is_accum_adapter_fixture
        else str(data.get("source_ref") or ""),
        protocol_id=str(data.get("protocol_id") or "accum_path_v1"),
        panel_kind=str(data.get("panel_kind") or "accum_components"),
        score_kind=str(data.get("score_kind") or "weighted_sleeves"),
    )
