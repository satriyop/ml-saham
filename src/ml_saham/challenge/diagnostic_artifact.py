"""Read-time verifier for non-promotable diagnostic artifact schema 4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import (
    DIAGNOSTIC_ARTIFACT_CONTRACT_ID,
    DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION,
)
from ml_saham.challenge.diagnostics.registry import load_diagnostic
from ml_saham.challenge.panel_diagnostic import build_diagnostic_panel
from ml_saham.challenge.protocols import get_protocol


class DiagnosticArtifactError(ValueError):
    """Artifact integrity or current upstream authority does not verify."""


def _canonical_digest(manifest: dict[str, Any]) -> str:
    material = {
        key: value
        for key, value in manifest.items()
        if key not in {"artifact_id", "content_digest", "created_at", "db_path"}
    }
    canonical = json.dumps(
        material,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_diagnostic_artifact(
    artifact_dir: Path | str, *, db_path: Path | str | None = None
) -> dict[str, Any]:
    root = Path(artifact_dir)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagnosticArtifactError("diagnostic manifest unreadable") from exc
    if not isinstance(manifest, dict):
        raise DiagnosticArtifactError("diagnostic manifest must be an object")
    if manifest.get("schema_version") != DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION:
        raise DiagnosticArtifactError("historical diagnostic artifact is display-only")
    if manifest.get("mode") not in {
        "challenge_diagnostic",
        "challenge_diagnostic_batch",
        "challenge_diagnostic_health",
    }:
        raise DiagnosticArtifactError("unsupported diagnostic artifact mode")
    if manifest.get("contract_id") != DIAGNOSTIC_ARTIFACT_CONTRACT_ID:
        raise DiagnosticArtifactError("diagnostic artifact contract mismatch")
    if manifest.get("non_promotable") is not True:
        raise DiagnosticArtifactError("diagnostic artifact must be non-promotable")
    digest = _canonical_digest(manifest)
    if manifest.get("content_digest") != digest:
        raise DiagnosticArtifactError("diagnostic artifact content digest mismatch")
    artifact_material = {
        "contract_id": DIAGNOSTIC_ARTIFACT_CONTRACT_ID,
        "content_digest": digest,
    }
    artifact_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(artifact_material, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    if manifest.get("artifact_id") != artifact_id:
        raise DiagnosticArtifactError("diagnostic artifact id mismatch")

    if manifest.get("mode") == "challenge_diagnostic_health":
        identity_map = manifest.get("diagnostic_identity_map")
        if not isinstance(identity_map, dict) or not identity_map:
            raise DiagnosticArtifactError("diagnostic health identity map missing")
        selected_db = (
            Path(db_path)
            if db_path is not None
            else Path(str(manifest.get("db_path") or ""))
        )
        action_id = str(manifest.get("observation_compatibility_id") or "")
        for child_id, child in identity_map.items():
            if not isinstance(child, dict):
                raise DiagnosticArtifactError(
                    "diagnostic health child identity malformed"
                )
            if child.get("blocked") is not None:
                continue
            spec = load_diagnostic(child_id)
            protocol = get_protocol(spec.protocol_id)
            rows, _notes, identity = build_diagnostic_panel(
                selected_db,
                spec,
                protocol.horizons_report,
                protocol.primary_horizon,
                compatibility_id=action_id,
                diagnostic_compatibility_id=str(
                    child.get("diagnostic_compatibility_id") or ""
                ),
            )
            expected_child = {
                "blocked": None,
                "diagnostic_compatibility_id": identity.diagnostic_compatibility_id,
                "producer_snapshot_ids": list(identity.producer_snapshot_ids),
                "producer_payload_digests": list(identity.producer_payload_digests),
                "producer_source_revisions": list(identity.producer_source_revisions),
                "diagnostic_spec_content_digest": spec.content_digest,
                "population_identity_id": identity.population_identity_id,
                "session_range": {
                    "start": identity.session_start,
                    "end": identity.session_end,
                },
                "cutoff_range": {
                    "start": identity.cutoff_start,
                    "end": identity.cutoff_end,
                },
                "n_rows": len(rows),
            }
            if child != expected_child:
                raise DiagnosticArtifactError(
                    f"diagnostic health identity stale for {child_id}"
                )
        return manifest

    diagnostic_id = manifest.get("diagnostic_id")
    protocol_id = manifest.get("protocol_id")
    if not isinstance(diagnostic_id, str) or not isinstance(protocol_id, str):
        raise DiagnosticArtifactError("diagnostic/spec identity missing")
    spec = load_diagnostic(diagnostic_id)
    protocol = get_protocol(protocol_id)
    selected_db = (
        Path(db_path)
        if db_path is not None
        else Path(str(manifest.get("db_path") or ""))
    )
    rows, _notes, identity = build_diagnostic_panel(
        selected_db,
        spec,
        protocol.horizons_report,
        protocol.primary_horizon,
        compatibility_id=str(manifest.get("observation_compatibility_id") or ""),
        diagnostic_compatibility_id=str(
            manifest.get("diagnostic_compatibility_id") or ""
        ),
    )
    expected = {
        "diagnostic_spec_content_digest": spec.content_digest,
        "observation_schema_version": identity.observation_schema_version,
        "producer_snapshot_ids": list(identity.producer_snapshot_ids),
        "producer_payload_digests": list(identity.producer_payload_digests),
        "producer_source_revisions": list(identity.producer_source_revisions),
        "action_policy_snapshot_ids": list(identity.action_policy_snapshot_ids),
        "action_policy_payload_digests": list(identity.action_policy_payload_digests),
        "action_policy_source_revisions": list(identity.action_policy_source_revisions),
        "population_identity_id": identity.population_identity_id,
        "session_range": {"start": identity.session_start, "end": identity.session_end},
        "cutoff_range": {"start": identity.cutoff_start, "end": identity.cutoff_end},
        "sample_unit": "ticker-session-window7",
        "n_rows": len(rows),
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise DiagnosticArtifactError(
                f"diagnostic artifact {field} is stale or invalid"
            )
    return manifest
