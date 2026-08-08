"""Load frozen DiagnosticSpecs (no ai-saham Python imports)."""

from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from importlib import resources
from pathlib import Path

from ml_saham.challenge.types import DiagnosticFeature, DiagnosticSpec

# diagnostic_id → packaged resource filename
_DIAG_FILES: dict[str, str] = {
    "mce.screen_display": "mce_screen_display.v1.json",
    "sector.peer_context": "sector_peer_context.v1.json",
    "institutional.accumulation_bag": "institutional_accumulation.v1.json",
    "company_quality.bag": "company_quality.v1.json",
}

DIAGNOSTIC_EXTRACTOR_CONTRACT_ID = "diagnostic_panel.schema14.window7.v1"
DIAGNOSTIC_REGIME_MAP = {
    "RISK_ON": 1.0,
    "NEUTRAL": 0.0,
    "RISK_OFF": -0.5,
    "VOLATILE": -1.0,
}


def diagnostic_spec_content_digest(
    spec_data: dict,
    *,
    extractor_contract_id: str = DIAGNOSTIC_EXTRACTOR_CONTRACT_ID,
    regime_map: dict[str, float] | None = None,
) -> str:
    integrity_payload = {
        "extractor_contract_id": extractor_contract_id,
        "regime_map": DIAGNOSTIC_REGIME_MAP if regime_map is None else regime_map,
        "spec": spec_data,
    }
    canonical = json.dumps(
        integrity_payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_diagnostic_ids() -> list[str]:
    return sorted(_DIAG_FILES)


def list_diagnostics() -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for did in list_diagnostic_ids():
        spec = load_diagnostic(did)
        out.append(
            {
                "diagnostic_id": spec.diagnostic_id,
                "version": spec.version,
                "hash": spec.hash,
                "engine": spec.engine,
                "scenario": spec.scenario,
                "protocol": spec.protocol_id,
                "n_features": len(spec.enabled_features()),
            }
        )
    return out


def _resolve_diagnostic_id(diagnostic_id: str) -> str:
    if diagnostic_id in _DIAG_FILES:
        return diagnostic_id
    # aliases: mce, screen_display, sector.peer, peer_context
    needle = diagnostic_id.strip().lower().replace("-", "_")
    for k in _DIAG_FILES:
        if needle == k.lower():
            return k
        if needle == k.split(".")[-1].lower():
            return k
        if needle == k.replace(".", "_"):
            return k
    known = ", ".join(list_diagnostic_ids())
    raise KeyError(f"Unknown diagnostic_id {diagnostic_id!r}. Known: {known}")


@lru_cache(maxsize=16)
def load_diagnostic(diagnostic_id: str) -> DiagnosticSpec:
    diagnostic_id = _resolve_diagnostic_id(diagnostic_id)
    name = _DIAG_FILES[diagnostic_id]
    here = Path(__file__).resolve().parent / name
    if here.is_file():
        data = json.loads(here.read_text(encoding="utf-8"))
    else:
        pkg = "ml_saham.challenge.diagnostics"
        with resources.files(pkg).joinpath(name).open("r", encoding="utf-8") as fh:
            data = json.load(fh)

    content_digest = diagnostic_spec_content_digest(data)
    feats = tuple(
        DiagnosticFeature(
            key=str(f["key"]),
            aliases=tuple(str(a) for a in f.get("aliases") or ()),
            enabled=bool(f.get("enabled", True)),
            note=str(f.get("note") or ""),
        )
        for f in data.get("features") or []
    )
    return DiagnosticSpec(
        diagnostic_id=str(data.get("diagnostic_id") or diagnostic_id),
        version=str(data.get("version") or "v1"),
        hash=str(data.get("hash") or ""),
        engine=str(data.get("engine") or ""),
        scenario=str(data.get("scenario") or "accum"),
        protocol_id=str(data.get("protocol_id") or "accum_path_v1"),
        features=feats,
        source=str(data.get("source") or ""),
        source_ref=str(data.get("source_ref") or ""),
        control_score=str(data.get("control_score") or "accum_production"),
        kind=str(data.get("kind") or "diagnostic"),
        banner=str(
            data.get("banner")
            or "ADR-057: not Action authority — display / promote-candidate only"
        ),
        content_digest=content_digest,
    )


def resolve_feature_key(spec: DiagnosticSpec, raw: str) -> str | None:
    """Map alias or key → canonical enabled feature key."""
    needle = raw.strip().lower().replace("-", "_")
    for f in spec.enabled_features():
        if f.key.lower() == needle or needle in {a.lower() for a in f.aliases}:
            return f.key
    return None
