"""Promote packet — human review checklist from challenge exports (no auto-apply)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import write_promote_packet
from ml_saham.challenge.champion import is_champion_against
from ml_saham.challenge.policies.registry import load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import (
    POLICY_VERSION,
    REQUIRED_POLICIES,
    stable_snapshot_id_for,
)
from ml_saham.challenge.protocols import get_protocol
from ml_saham.challenge.types import PromotePacketResult

_REQUIRED = (
    "status",
    "policy_id",
    "protocol_id",
    "baseline_id",
    "against_id",
)

_VERIFIED_PRODUCTION_IDENTITY = (
    "observation_compatibility_id",
    "production_snapshot_id",
    "production_snapshot_digest",
    "production_policy_id",
    "production_policy_version",
    "production_semantic_engine_contract_id",
    "challenge_adapter_id",
    "challenge_adapter_version",
)

# Challenge artifact writers emit schema_version: 2 (manifests / promote packs).
SUPPORTED_ARTIFACT_SCHEMA_VERSIONS = frozenset({2})

# production_snapshot_id and production_snapshot_digest are raw sha256 hex digests.
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
# Observation cohorts are free-form but must not be trivial placeholders.
_MIN_COMPAT_LEN = 8


def validate_verified_production_identity(
    data: dict[str, Any],
    *,
    require_schema_version: bool = False,
) -> str | None:
    """Validate formats and consistency of production identities for promote reopen.

    Presence of identity fields is checked separately. This layer rejects
    fabricated non-empty placeholders that would otherwise look "verified."

    Returns an error string, or ``None`` when valid.
    """
    # --- artifact schema (when present or required for artifact-shaped packs) ---
    if require_schema_version or "schema_version" in data:
        raw_sv = data.get("schema_version")
        if raw_sv is None or raw_sv == "":
            return (
                "invalid artifact schema_version: missing "
                f"(supported: {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)})"
            )
        try:
            schema_version = int(raw_sv)
        except (TypeError, ValueError):
            return (
                f"invalid artifact schema_version: {raw_sv!r} "
                f"(supported: {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)})"
            )
        if schema_version not in SUPPORTED_ARTIFACT_SCHEMA_VERSIONS:
            return (
                f"unsupported artifact schema_version={schema_version} "
                f"(supported: {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)})"
            )

    policy_id = str(data.get("policy_id") or "").strip()
    prod_policy_id = str(data.get("production_policy_id") or "").strip()
    if not policy_id:
        return "production identity invalid: policy_id is empty"
    if prod_policy_id != policy_id:
        return (
            "production identity invalid: production_policy_id="
            f"{prod_policy_id!r} does not equal policy_id={policy_id!r}"
        )

    if policy_id not in REQUIRED_POLICIES:
        return (
            "production identity invalid: policy_id="
            f"{policy_id!r} is not a verified production policy eligible for promote"
        )

    compat = str(data.get("observation_compatibility_id") or "").strip()
    if len(compat) < _MIN_COMPAT_LEN:
        return (
            "production identity invalid: observation_compatibility_id format "
            f"(need non-empty id with length ≥ {_MIN_COMPAT_LEN}, got {compat!r})"
        )

    snap_id = str(data.get("production_snapshot_id") or "").strip().lower()
    digest = str(data.get("production_snapshot_digest") or "").strip().lower()
    if not _HEX64_RE.fullmatch(snap_id):
        return (
            "production identity invalid: production_snapshot_id format "
            f"(need 64 lowercase hex chars, got {snap_id!r})"
        )
    if not _HEX64_RE.fullmatch(digest):
        return (
            "production identity invalid: production_snapshot_digest format "
            f"(need 64 lowercase hex chars, got {digest!r})"
        )

    prod_version = str(data.get("production_policy_version") or "").strip()
    if prod_version != POLICY_VERSION:
        return (
            "production identity invalid: production_policy_version="
            f"{prod_version!r} does not match expected {POLICY_VERSION!r}"
        )

    _decision_type, expected_semantic = REQUIRED_POLICIES[policy_id]
    semantic = str(data.get("production_semantic_engine_contract_id") or "").strip()
    if semantic != expected_semantic:
        return (
            "production identity invalid: production_semantic_engine_contract_id="
            f"{semantic!r} does not match expected {expected_semantic!r} "
            f"for policy {policy_id}"
        )

    protocol_id = str(data.get("protocol_id") or "").strip()
    adapter_id = str(data.get("challenge_adapter_id") or "").strip()
    adapter_version = str(data.get("challenge_adapter_version") or "").strip()

    try:
        adapter = load_policy_adapter(policy_id)
    except KeyError as exc:
        return (
            "production identity invalid: no supported challenge adapter for "
            f"policy_id={policy_id!r}: {exc}"
        )

    if adapter_id != adapter.adapter_id:
        return (
            "production identity invalid: challenge_adapter_id="
            f"{adapter_id!r} does not match supported adapter "
            f"{adapter.adapter_id!r}"
        )
    if adapter_version != adapter.adapter_version:
        return (
            "production identity invalid: challenge_adapter_version="
            f"{adapter_version!r} does not match supported adapter version "
            f"{adapter.adapter_version!r}"
        )
    if protocol_id != adapter.protocol_id:
        return (
            "production identity invalid: protocol_id="
            f"{protocol_id!r} does not match adapter protocol "
            f"{adapter.protocol_id!r}"
        )
    try:
        get_protocol(protocol_id)
    except KeyError:
        return (
            "production identity invalid: unknown or unsupported "
            f"protocol_id={protocol_id!r}"
        )
    if semantic not in adapter.supported_semantic_engine_contract_ids:
        return (
            "production identity invalid: semantic contract "
            f"{semantic!r} is not supported by adapter {adapter.adapter_id!r}"
        )

    # Snapshot-id recomputation: cohort + policy identity under shipped contract.
    expected_snapshot_id = stable_snapshot_id_for(
        compatibility_id=compat,
        policy_id=policy_id,
    )
    if expected_snapshot_id != snap_id:
        return (
            "production identity invalid: production_snapshot_id does not match "
            "recomputed snapshot identity for compatibility_id+policy_id "
            "(identity mismatch; not merely missing fields)"
        )

    return None


def _after_presence_checks(
    data: dict[str, Any],
    *,
    require_schema_version: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """Shared presence + validity gate used by JSON and artifact loaders."""
    missing = [k for k in _REQUIRED if k not in data or data[k] in (None, "")]
    if missing:
        return None, f"missing required fields: {', '.join(missing)}"
    missing_identity = [k for k in _VERIFIED_PRODUCTION_IDENTITY if not data.get(k)]
    if missing_identity:
        return None, (
            "historical artifact is not eligible for a verified production-policy "
            "promotion packet; missing: " + ", ".join(missing_identity)
        )
    validity_err = validate_verified_production_identity(
        data, require_schema_version=require_schema_version
    )
    if validity_err is not None:
        return None, validity_err
    return data, None


def load_evidence_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read JSON: {exc}"
    if not isinstance(data, dict):
        return None, "export root must be a JSON object"
    # Bare challenge export JSON may omit schema_version; still validate identities.
    # If schema_version is present, it must be supported.
    return _after_presence_checks(data, require_schema_version=False)


def load_evidence_artifact(dir_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load from challenge artifact dir (metrics.json + manifest) or champion export style."""
    if not dir_path.is_dir():
        return None, f"not a directory: {dir_path}"
    # Prefer full export if present
    for name in ("export.json", "result.json", "champion.json"):
        p = dir_path / name
        if p.is_file():
            return load_evidence_json(p)
    manifest_p = dir_path / "manifest.json"
    metrics_p = dir_path / "metrics.json"
    if not manifest_p.is_file():
        return None, "artifact dir missing manifest.json (or export.json)"
    try:
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        metrics = (
            json.loads(metrics_p.read_text(encoding="utf-8"))
            if metrics_p.is_file()
            else {}
        )
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read artifact: {exc}"
    # Map challenge artifact layout; schema_version is required for manifest packs.
    data = {
        "schema_version": manifest.get("schema_version"),
        "status": metrics.get("status") or manifest.get("status"),
        "policy_id": manifest.get("policy_id"),
        "protocol_id": manifest.get("protocol_id"),
        "policy_hash": manifest.get("policy_hash"),
        "baseline_id": manifest.get("baseline_id") or "production",
        "against_id": manifest.get("against_id"),
        "primary_horizon": manifest.get("primary_horizon"),
        "primary_ic_baseline": metrics.get("primary_ic_baseline"),
        "primary_ic_against": metrics.get("primary_ic_against"),
        "n_rows": manifest.get("n_rows"),
        "fold_metrics": metrics.get("fold_metrics") or [],
        "weights": {},
        "notes": [],
        "mode": manifest.get("mode"),
    }
    for key in _VERIFIED_PRODUCTION_IDENTITY:
        data[key] = manifest.get(key)
    weights_p = dir_path / "weights.json"
    if weights_p.is_file():
        try:
            data["weights"] = json.loads(weights_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return _after_presence_checks(data, require_schema_version=True)


def _fmt_ic(x: Any) -> str:
    try:
        if x is None:
            return "n/a"
        return f"{float(x):+.4f}"
    except (TypeError, ValueError):
        return "n/a"


def build_promote_md(evidence: dict[str, Any], *, mode: str) -> str:
    status = str(evidence.get("status") or "")
    title = (
        "# Promote review — NOT applied"
        if status == "WIN"
        else "# Promote / reject review — NOT applied"
    )
    lines = [
        title,
        "",
        "> ml-saham **never** writes ai-saham config. This packet is human decision support only.",
        "",
        "## Evidence (auto-filled)",
        "",
        f"- **Mode:** {mode}",
        f"- **Policy:** `{evidence.get('policy_id')}`",
        f"- **Policy hash:** `{evidence.get('policy_hash') or 'n/a'}`",
        f"- **Observation cohort:** `{evidence.get('observation_compatibility_id')}`",
        f"- **Production snapshot:** `{evidence.get('production_snapshot_id')}`",
        f"- **Production digest:** `{evidence.get('production_snapshot_digest')}`",
        f"- **Production semantic contract:** "
        f"`{evidence.get('production_semantic_engine_contract_id')}`",
        f"- **Challenge adapter:** `{evidence.get('challenge_adapter_id')}` "
        f"`{evidence.get('challenge_adapter_version')}`",
        f"- **Protocol:** `{evidence.get('protocol_id')}`",
        f"- **Baseline:** `{evidence.get('baseline_id')}`",
        f"- **Against:** `{evidence.get('against_id')}`",
        f"- **Status:** **{status}**",
        f"- **Primary horizon:** {evidence.get('primary_horizon')}",
        f"- **IC production:** {_fmt_ic(evidence.get('primary_ic_baseline'))}",
        f"- **IC against:** {_fmt_ic(evidence.get('primary_ic_against'))}",
        f"- **n_rows:** {evidence.get('n_rows')}",
        "",
        "### Weights / importances",
        "",
        "```json",
        json.dumps(evidence.get("weights") or {}, indent=2)[:4000],
        "```",
        "",
        "### Notes",
        "",
    ]
    for n in (evidence.get("notes") or [])[-12:]:
        lines.append(f"- {n}")
    if mode == "champion":
        lines.extend(
            [
                "",
                "### Champion emphasis",
                "",
                "- WIN implies a **scorer replacement** candidate, not a small weight tweak.",
                "- Confirm train-only fit / fold stability before any ai-saham change.",
            ]
        )
    lines.extend(
        [
            "",
            "## Human checklist",
            "",
            "- [ ] I understand ml-saham never writes ai-saham config",
            "- [ ] Protocol + policy_hash match the live question I care about",
            "- [ ] Status is WIN or I accept INCONCLUSIVE/LOSE with explicit reason",
            "- [ ] WIN rests on ≥2 valid OOS folds (single-fold edge is provisional INCONCLUSIVE only)",
            "- [ ] Fold table / n_train reviewed (not one lucky fold)",
            "- [ ] Gross costs disclaimer accepted",
            "- [ ] Proposed change stated in one sentence (weights / drop factor / scorer)",
            "- [ ] Target ai-saham file/use-case named by human",
            "",
            "## Decision (fill in)",
            "",
            "- **Decision:** promote / reject / need more data",
            "- **Rationale:**",
            "- **ai-saham change (if any):**",
            "",
        ]
    )
    return "\n".join(lines)


def build_promote_packet(
    *,
    from_json: Path | None = None,
    from_artifact: Path | None = None,
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> PromotePacketResult:
    if from_json is None and from_artifact is None:
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error="require --from-json PATH or --from-artifact DIR",
            lines=["BLOCKED: require --from-json or --from-artifact"],
        )
    if from_json is not None and from_artifact is not None:
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error="use only one of --from-json or --from-artifact",
            lines=["BLOCKED: use only one input source"],
        )

    if from_json is not None:
        evidence, err = load_evidence_json(Path(from_json))
    else:
        evidence, err = load_evidence_artifact(Path(from_artifact))  # type: ignore[arg-type]

    if err or evidence is None:
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error=err or "load failed",
            lines=[f"BLOCKED: {err}"],
        )

    against = str(evidence.get("against_id") or "")
    mode = str(evidence.get("mode") or "")
    if mode not in ("tune", "champion"):
        mode = "champion" if is_champion_against(against) else "tune"

    md = build_promote_md(evidence, mode=mode)
    result = PromotePacketResult(
        policy_id=str(evidence.get("policy_id") or ""),
        mode=mode,
        summary_md=md,
        lines=[
            "=== PROMOTE PACKET (NOT APPLIED) ===",
            f"Policy: {evidence.get('policy_id')}",
            f"Mode: {mode} · Status: {evidence.get('status')}",
            f"Against: {against}",
        ],
        evidence=evidence,
    )
    if write_artifact:
        write_promote_packet(result, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
            result.lines.append(f"Open: {result.artifact_dir / 'PROMOTE.md'}")
    return result
