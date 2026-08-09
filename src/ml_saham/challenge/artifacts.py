"""Write challenge run artifact packs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from ml_saham.artifacts.writer import resolve_artifacts_root
from ml_saham.challenge.champion import is_champion_against
from ml_saham.challenge.types import (
    BatchDiagnosticResult,
    BatchFactorResult,
    ChallengeResult,
    DiagnosticChallengeResult,
    EnginePortfolioResult,
    FactorChallengeResult,
    HealthReportResult,
    PromotePacketResult,
)

JAKARTA = ZoneInfo("Asia/Jakarta")

# Challenge product artifact / promote-reopen contract (integer, not coerced).
# Distinct from curriculum pack SCHEMA_VERSION in ml_saham.artifacts.writer.
#
# v5 (promote-evidence): sealed digests + pack_binding + fold_geometry_contract_id
#     ``session_native_purged.v1`` with per-fold session geometry fields.
# v4: sealed digests only — **historical / display-only** (pre ML-OOS-01 geometry
#     enforcement; may contain broken row-based splits).
# v3 display artifacts: factor/diagnostic/batch/engine/health/promote-packet
#     writers stamp this without seals. v2 and earlier remain historical.
# Promote reopen accepts only schema v5 sealed evidence with geometry contract.
CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION = 5
CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION = 3
DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION = 4
DIAGNOSTIC_ARTIFACT_CONTRACT_ID = "diagnostic_result_artifact.v4"

# Material identity for purged fold construction (sealed into content_digest).
FOLD_GEOMETRY_CONTRACT_ID = "session_native_purged.v1"


def _seal_diagnostic_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
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
    content_digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    artifact_material = {
        "contract_id": DIAGNOSTIC_ARTIFACT_CONTRACT_ID,
        "content_digest": content_digest,
    }
    artifact_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(artifact_material, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    return {**manifest, "content_digest": content_digest, "artifact_id": artifact_id}


# Alias used by sealed promote-evidence writers/export path.
CHALLENGE_ARTIFACT_SCHEMA_VERSION = CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION
# Historical schemas still readable for display, never for promote reopen.
# v4 sealed packs predate fold_geometry_contract_id enforcement (ML-OOS-01).
HISTORICAL_CHALLENGE_ARTIFACT_SCHEMA_VERSIONS = frozenset({1, 2, 3, 4})

# Closed payload for content_digest (excludes operational paths and digests).
_CONTENT_DIGEST_KEYS: tuple[str, ...] = (
    "schema_version",
    "mode",
    "status",
    "policy_id",
    "protocol_id",
    "policy_hash",
    "observation_compatibility_id",
    "production_snapshot_id",
    "production_snapshot_digest",
    "production_policy_id",
    "production_policy_version",
    "production_semantic_engine_contract_id",
    "challenge_adapter_id",
    "challenge_adapter_version",
    "baseline_id",
    "against_id",
    "population_identity_kind",
    "population_identity_id",
    "population_identity_detail",
    "fold_geometry_contract_id",
    "n_rows",
    "primary_horizon",
    "primary_ic_baseline",
    "primary_ic_against",
    "horizon_metrics",
    "fold_metrics",
    "weights",
    "notes",
)


def canonical_challenge_json(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON for challenge evidence digests."""
    return json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def challenge_content_digest(payload: Mapping[str, Any]) -> str:
    """sha256 hex of closed challenge evidence fields (no self-reference)."""
    material = {k: payload.get(k) for k in _CONTENT_DIGEST_KEYS}
    return hashlib.sha256(
        canonical_challenge_json(material).encode("utf-8")
    ).hexdigest()


def challenge_artifact_id(
    *, content_digest: str, policy_id: str, against_id: str
) -> str:
    """Stable identity for one sealed challenge evidence payload."""
    material = {
        "content_digest": content_digest,
        "policy_id": policy_id,
        "against_id": against_id,
    }
    return hashlib.sha256(
        canonical_challenge_json(material).encode("utf-8")
    ).hexdigest()


def stamp_challenge_evidence_digests(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with content_digest and artifact_id stamped (schema v5)."""
    out = dict(payload)
    out["schema_version"] = CHALLENGE_ARTIFACT_SCHEMA_VERSION
    out["fold_geometry_contract_id"] = FOLD_GEOMETRY_CONTRACT_ID
    digest = challenge_content_digest(out)
    out["content_digest"] = digest
    out["artifact_id"] = challenge_artifact_id(
        content_digest=digest,
        policy_id=str(out.get("policy_id") or ""),
        against_id=str(out.get("against_id") or ""),
    )
    return out


def file_sha256_hex(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def challenge_result_export_payload(
    result: ChallengeResult,
    *,
    mode: str | None = None,
    artifact_dir: Path | str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a promote-eligible challenge/champion JSON export (schema stamped).

    Used by CLI ``--export-json``, health champion packs, and tests. Always
    emits integer ``schema_version`` matching writer manifests, plus v5 digests
    and ``fold_geometry_contract_id``.
    """
    resolved_mode = mode
    if resolved_mode is None:
        resolved_mode = "champion" if is_champion_against(result.against_id) else "tune"
    art = artifact_dir
    if art is None and result.artifact_dir is not None:
        art = result.artifact_dir
    payload: dict[str, Any] = {
        "schema_version": CHALLENGE_ARTIFACT_SCHEMA_VERSION,
        "mode": resolved_mode,
        "status": result.status.value,
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "observation_compatibility_id": result.observation_compatibility_id,
        "production_snapshot_id": result.production_snapshot_id,
        "production_snapshot_digest": result.production_snapshot_digest,
        "production_policy_id": result.production_policy_id,
        "production_policy_version": result.production_policy_version,
        "production_semantic_engine_contract_id": (
            result.production_semantic_engine_contract_id
        ),
        "challenge_adapter_id": result.challenge_adapter_id,
        "challenge_adapter_version": result.challenge_adapter_version,
        "baseline_id": result.baseline_id,
        "against_id": result.against_id,
        "population_identity_kind": result.population_identity_kind,
        "population_identity_id": result.population_identity_id,
        "population_identity_detail": result.population_identity_detail,
        "fold_geometry_contract_id": FOLD_GEOMETRY_CONTRACT_ID,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "primary_ic_baseline": result.primary_ic_baseline,
        "primary_ic_against": result.primary_ic_against,
        "horizon_metrics": result.horizon_metrics,
        "fold_metrics": result.fold_metrics,
        "weights": result.weights,
        "notes": result.notes,
        "artifact_dir": str(art) if art is not None else None,
    }
    if extra:
        payload.update(extra)
    return stamp_challenge_evidence_digests(payload)


def write_challenge_artifact(
    result: ChallengeResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write a sealed v5 promote-evidence pack via owned temp dir + atomic rename."""
    import errno
    import os
    import shutil
    import tempfile
    import uuid

    root = resolve_artifacts_root(artifacts_root)
    parent = root / "challenge" / result.policy_id.replace("/", ".")
    parent.mkdir(parents=True, exist_ok=True)

    # Pre-seal without final path so we can name the directory after artifact_id.
    sealed_seed = challenge_result_export_payload(
        result, mode="challenge_run", artifact_dir=None, extra=extra
    )
    artifact_id = str(sealed_seed["artifact_id"])
    # Unique final name from the start (no check-then-rename race window).
    publish_token = uuid.uuid4().hex
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S_%f")
    final = parent / f"{ts}_{artifact_id[:12]}_{publish_token[:12]}"

    # Owned temporary directory only (never delete another writer's path).
    tmp_path = Path(
        tempfile.mkdtemp(prefix=f".pack_{artifact_id[:12]}_", dir=str(parent))
    )
    owned_tmp = tmp_path

    sealed = challenge_result_export_payload(
        result, mode="challenge_run", artifact_dir=final, extra=extra
    )
    metrics = {
        "primary_ic_baseline": result.primary_ic_baseline,
        "primary_ic_against": result.primary_ic_against,
        "horizon_metrics": result.horizon_metrics,
        "fold_metrics": result.fold_metrics,
        "notes": result.notes,
        "status": result.status.value,
        "content_digest": sealed["content_digest"],
        "artifact_id": sealed["artifact_id"],
    }
    weights = result.weights
    manifest = {
        "schema_version": CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION,
        "mode": "challenge_run",
        "track": "policy_tournament",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "observation_compatibility_id": result.observation_compatibility_id,
        "production_snapshot_id": result.production_snapshot_id,
        "production_snapshot_digest": result.production_snapshot_digest,
        "production_policy_id": result.production_policy_id,
        "production_policy_version": result.production_policy_version,
        "production_semantic_engine_contract_id": (
            result.production_semantic_engine_contract_id
        ),
        "challenge_adapter_id": result.challenge_adapter_id,
        "challenge_adapter_version": result.challenge_adapter_version,
        "baseline_id": result.baseline_id,
        "against_id": result.against_id,
        "population_identity_kind": result.population_identity_kind,
        "population_identity_id": result.population_identity_id,
        "population_identity_detail": result.population_identity_detail,
        "fold_geometry_contract_id": FOLD_GEOMETRY_CONTRACT_ID,
        "status": result.status.value,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "content_digest": sealed["content_digest"],
        "artifact_id": sealed["artifact_id"],
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
    }
    if extra:
        manifest["extra"] = extra

    try:
        for name, payload in (
            ("metrics.json", metrics),
            ("weights.json", weights),
            ("manifest.json", manifest),
        ):
            path = tmp_path / name
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with path.open("rb") as fh:
                fh.flush()
                os.fsync(fh.fileno())
        pack_binding = {
            "schema_version": CHALLENGE_PROMOTE_EVIDENCE_SCHEMA_VERSION,
            "artifact_id": sealed["artifact_id"],
            "content_digest": sealed["content_digest"],
            "members": ["manifest.json", "metrics.json", "weights.json"],
            "file_digests": {
                "manifest.json": file_sha256_hex(tmp_path / "manifest.json"),
                "metrics.json": file_sha256_hex(tmp_path / "metrics.json"),
                "weights.json": file_sha256_hex(tmp_path / "weights.json"),
            },
        }
        binding_path = tmp_path / "pack_binding.json"
        binding_path.write_text(
            json.dumps(pack_binding, indent=2) + "\n", encoding="utf-8"
        )
        with binding_path.open("rb") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        (tmp_path / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
        # Atomic publish with rename retry if destination somehow collides.
        published = False
        for attempt in range(8):
            dest = (
                final
                if attempt == 0
                else (parent / f"{ts}_{artifact_id[:12]}_{uuid.uuid4().hex[:12]}")
            )
            try:
                os.replace(str(tmp_path), str(dest))
                final = dest
                published = True
                owned_tmp = None
                break
            except OSError as exc:
                # EEXIST/ENOTEMPTY (macOS Directory not empty is errno 66).
                if exc.errno not in {
                    errno.EEXIST,
                    getattr(errno, "ENOTEMPTY", 66),
                    66,
                }:
                    raise
                continue
        if not published:
            raise OSError(f"could not atomically publish challenge pack under {parent}")
    except Exception:
        if owned_tmp is not None and owned_tmp.exists():
            # Only remove the temp directory we created in this call.
            shutil.rmtree(owned_tmp, ignore_errors=True)
        raise

    result.artifact_dir = final
    return final


def write_factor_artifact(
    result: FactorChallengeResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = (
        root
        / "challenge"
        / "factor"
        / result.policy_id.replace("/", ".")
        / result.factor
        / ts
    )
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_factor",
        "track": "factor_validity",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "observation_compatibility_id": result.observation_compatibility_id,
        "production_snapshot_id": result.production_snapshot_id,
        "production_snapshot_digest": result.production_snapshot_digest,
        "production_policy_id": result.production_policy_id,
        "production_policy_version": result.production_policy_version,
        "production_semantic_engine_contract_id": (
            result.production_semantic_engine_contract_id
        ),
        "challenge_adapter_id": result.challenge_adapter_id,
        "challenge_adapter_version": result.challenge_adapter_version,
        "factor": result.factor,
        "verdict": result.verdict.value,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    metrics = {
        "verdict": result.verdict.value,
        "mean_delta_ic": result.mean_delta_ic,
        "mean_univariate_ic": result.mean_univariate_ic,
        "fold_agree_positive_delta": result.fold_agree_positive_delta,
        "horizon_metrics": result.horizon_metrics,
        "fold_metrics": result.fold_metrics,
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


def write_batch_factor_artifact(
    result: BatchFactorResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = (
        root / "challenge" / "factor" / result.policy_id.replace("/", ".") / "_all" / ts
    )
    out.mkdir(parents=True, exist_ok=True)
    factors_payload = [
        {
            "factor": r.factor,
            "verdict": r.verdict.value,
            "mean_delta_ic": r.mean_delta_ic,
            "mean_univariate_ic": r.mean_univariate_ic,
            "fold_agree_positive_delta": r.fold_agree_positive_delta,
            "notes": r.notes[-3:],
        }
        for r in result.results
    ]
    manifest = {
        "schema_version": CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_factor_batch",
        "track": "factor_validity_batch",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "observation_compatibility_id": result.observation_compatibility_id,
        "production_snapshot_id": result.production_snapshot_id,
        "production_snapshot_digest": result.production_snapshot_digest,
        "production_policy_id": result.production_policy_id,
        "production_policy_version": result.production_policy_version,
        "production_semantic_engine_contract_id": (
            result.production_semantic_engine_contract_id
        ),
        "challenge_adapter_id": result.challenge_adapter_id,
        "challenge_adapter_version": result.challenge_adapter_version,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "n_factors": len(result.results),
        "blocked": result.blocked.value if result.blocked else None,
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "factors": [f["factor"] for f in factors_payload],
        "verdicts": {f["factor"]: f["verdict"] for f in factors_payload},
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out / "metrics.json").write_text(
        json.dumps({"factors": factors_payload}, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


def write_diagnostic_artifact(
    result: DiagnosticChallengeResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    feat = result.feature.replace("/", ".")
    out = (
        root
        / "challenge"
        / "diagnostic"
        / result.diagnostic_id.replace("/", ".")
        / feat
        / ts
    )
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_diagnostic",
        "non_promotable": True,
        "contract_id": DIAGNOSTIC_ARTIFACT_CONTRACT_ID,
        "track": "diagnostic_validity",
        "diagnostic_id": result.diagnostic_id,
        "protocol_id": result.protocol_id,
        "diagnostic_hash": result.diagnostic_hash,
        "diagnostic_spec_content_digest": result.diagnostic_spec_content_digest,
        "observation_compatibility_id": result.observation_compatibility_id,
        "diagnostic_compatibility_id": result.diagnostic_compatibility_id,
        "producer_snapshot_ids": list(result.producer_snapshot_ids),
        "producer_payload_digests": list(result.producer_payload_digests),
        "producer_source_revisions": list(result.producer_source_revisions),
        "action_policy_snapshot_ids": list(result.action_policy_snapshot_ids),
        "action_policy_payload_digests": list(result.action_policy_payload_digests),
        "action_policy_source_revisions": list(result.action_policy_source_revisions),
        "observation_schema_version": result.observation_schema_version,
        "population_identity_kind": "accum_membership_digest",
        "population_identity_id": result.population_identity_id,
        "session_range": {"start": result.session_start, "end": result.session_end},
        "cutoff_range": {"start": result.cutoff_start, "end": result.cutoff_end},
        "sample_unit": "ticker-session-window7",
        "feature": result.feature,
        "verdict": result.verdict.value,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "banner": "ADR-057: not Action authority",
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
    }
    manifest = _seal_diagnostic_manifest(manifest)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    metrics = {
        "verdict": result.verdict.value,
        "coverage": result.coverage,
        "mean_univariate_ic": result.mean_univariate_ic,
        "mean_residual_ic": result.mean_residual_ic,
        "mean_redundancy": result.mean_redundancy,
        "fold_agree_residual_positive": result.fold_agree_residual_positive,
        "horizon_metrics": result.horizon_metrics,
        "fold_metrics": result.fold_metrics,
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


def write_batch_diagnostic_artifact(
    result: BatchDiagnosticResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = (
        root
        / "challenge"
        / "diagnostic"
        / result.diagnostic_id.replace("/", ".")
        / "_all"
        / ts
    )
    out.mkdir(parents=True, exist_ok=True)
    factors_payload = [
        {
            "feature": r.feature,
            "diagnostic_id": r.diagnostic_id,
            "verdict": r.verdict.value,
            "coverage": r.coverage,
            "mean_univariate_ic": r.mean_univariate_ic,
            "mean_residual_ic": r.mean_residual_ic,
            "mean_redundancy": r.mean_redundancy,
            "notes": r.notes[-3:],
        }
        for r in result.results
    ]
    is_health = result.diagnostic_id.startswith("_health.")
    manifest = {
        "schema_version": DIAGNOSTIC_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_diagnostic_health"
        if is_health
        else "challenge_diagnostic_batch",
        "non_promotable": True,
        "contract_id": DIAGNOSTIC_ARTIFACT_CONTRACT_ID,
        "track": "diagnostic_validity_batch",
        "diagnostic_id": result.diagnostic_id,
        "protocol_id": result.protocol_id,
        "diagnostic_hash": result.diagnostic_hash,
        "diagnostic_spec_content_digest": result.diagnostic_spec_content_digest,
        "observation_compatibility_id": result.observation_compatibility_id,
        "diagnostic_compatibility_id": result.diagnostic_compatibility_id,
        "producer_snapshot_ids": list(result.producer_snapshot_ids),
        "producer_payload_digests": list(result.producer_payload_digests),
        "producer_source_revisions": list(result.producer_source_revisions),
        "action_policy_snapshot_ids": list(result.action_policy_snapshot_ids),
        "action_policy_payload_digests": list(result.action_policy_payload_digests),
        "action_policy_source_revisions": list(result.action_policy_source_revisions),
        "observation_schema_version": result.observation_schema_version,
        "diagnostic_identity_map": result.diagnostic_identity_map,
        "population_identity_kind": "accum_membership_digest",
        "population_identity_id": result.population_identity_id,
        "session_range": {"start": result.session_start, "end": result.session_end},
        "cutoff_range": {"start": result.cutoff_start, "end": result.cutoff_end},
        "sample_unit": "ticker-session-window7",
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "n_features": len(result.results),
        "blocked": result.blocked.value if result.blocked else None,
        "banner": "ADR-057: not Action authority",
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "features": [f["feature"] for f in factors_payload],
        "verdicts": {f["feature"]: f["verdict"] for f in factors_payload},
    }
    manifest = _seal_diagnostic_manifest(manifest)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out / "metrics.json").write_text(
        json.dumps({"features": factors_payload}, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


def write_engine_artifact(
    result: EnginePortfolioResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = root / "challenge" / "engine" / result.engine_id / ts
    out.mkdir(parents=True, exist_ok=True)
    rows_payload = [
        {
            "scenario": r.scenario,
            "policy_id": r.policy_id,
            "protocol_id": r.protocol_id,
            "policy_hash": r.policy_hash,
            "status": r.status,
            "n_rows": r.n_rows,
            "primary_horizon": r.primary_horizon,
            "primary_ic_baseline": r.primary_ic_baseline,
            "primary_ic_against": r.primary_ic_against,
            "against_id": r.against_id,
            "notes": r.notes[-5:],
            "error": r.error,
            "observation_compatibility_id": r.observation_compatibility_id,
            "production_snapshot_id": r.production_snapshot_id,
            "production_snapshot_digest": r.production_snapshot_digest,
            "production_policy_id": r.production_policy_id,
            "production_policy_version": r.production_policy_version,
            "production_semantic_engine_contract_id": (
                r.production_semantic_engine_contract_id
            ),
            "challenge_adapter_id": r.challenge_adapter_id,
            "challenge_adapter_version": r.challenge_adapter_version,
        }
        for r in result.rows
    ]
    manifest = {
        "schema_version": CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_engine",
        "engine_id": result.engine_id,
        "scenario_filter": result.scenario_filter,
        "against_id": result.against_id,
        "baseline_id": result.baseline_id,
        "counts": result.counts,
        "n_policies": len(result.rows),
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "policies": [r.policy_id for r in result.rows],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out / "rollup.json").write_text(
        json.dumps(
            {
                "engine_id": result.engine_id,
                "scenario_filter": result.scenario_filter,
                "against_id": result.against_id,
                "counts": result.counts,
                "notes": result.notes,
                "rows": rows_payload,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


def write_health_artifact(
    result: HealthReportResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = root / "challenge" / "health" / ts
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_health",
        "engine_id": result.engine_id,
        "scenario_filter": result.scenario_filter,
        "with_champion": result.with_champion,
        "with_factors": result.with_factors,
        "with_diagnostics": result.with_diagnostics,
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "n_index": len(result.index),
        "production_identities": result.production_identities,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    (out / "engine.json").write_text(
        json.dumps(result.engine_payload, indent=2) + "\n", encoding="utf-8"
    )
    (out / "index.json").write_text(
        json.dumps(result.index, indent=2) + "\n", encoding="utf-8"
    )
    if result.champion_payload is not None:
        (out / "champion.json").write_text(
            json.dumps(result.champion_payload, indent=2) + "\n", encoding="utf-8"
        )
    if result.factors_payload is not None:
        (out / "factors.json").write_text(
            json.dumps(result.factors_payload, indent=2) + "\n", encoding="utf-8"
        )
    if result.diagnostics_payload is not None:
        (out / "diagnostics.json").write_text(
            json.dumps(result.diagnostics_payload, indent=2) + "\n", encoding="utf-8"
        )
    result.artifact_dir = out
    return out


def write_promote_packet(
    result: PromotePacketResult,
    *,
    artifacts_root: Path | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    safe = result.policy_id.replace("/", ".")
    out = root / "challenge" / "promote" / safe / ts
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": CHALLENGE_DISPLAY_ARTIFACT_SCHEMA_VERSION,
        "mode": "challenge_promote_packet",
        "policy_id": result.policy_id,
        **{
            key: result.evidence.get(key)
            for key in (
                "observation_compatibility_id",
                "production_snapshot_id",
                "production_snapshot_digest",
                "production_policy_id",
                "production_policy_version",
                "production_semantic_engine_contract_id",
                "challenge_adapter_id",
                "challenge_adapter_version",
                "protocol_id",
            )
        },
        "purpose_mode": result.mode,
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "auto_applied": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out / "PROMOTE.md").write_text(result.summary_md or "", encoding="utf-8")
    (out / "evidence.json").write_text(
        json.dumps(result.evidence, indent=2) + "\n", encoding="utf-8"
    )
    result.artifact_dir = out
    return out
