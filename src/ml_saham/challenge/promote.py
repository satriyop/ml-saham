"""Promote packet — human review checklist from challenge exports (no auto-apply)."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import (
    CHALLENGE_ARTIFACT_SCHEMA_VERSION,
    write_promote_packet,
)
from ml_saham.challenge.champion import is_champion_against
from ml_saham.challenge.policies.registry import load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import (
    POLICY_VERSION,
    REQUIRED_POLICIES,
    stable_snapshot_id_for,
    verify_export_snapshot_against_db,
)
from ml_saham.challenge.protocols import get_protocol
from ml_saham.challenge.types import PromotePacketResult
from ml_saham.data.aisaham_read import connect as aisaham_connect
from ml_saham.data.connection import resolve_db_path

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

# Challenge artifact schema v3 material population identity (required on reopen).
_POPULATION_IDENTITY_V3 = (
    "population_identity_kind",
    "population_identity_id",
    "population_identity_detail",
)
_ACCUM_POPULATION_KIND = "accum_compat"

# Exact integer contract; writers stamp CHALLENGE_ARTIFACT_SCHEMA_VERSION.
SUPPORTED_ARTIFACT_SCHEMA_VERSIONS = frozenset({CHALLENGE_ARTIFACT_SCHEMA_VERSION})

# production_snapshot_id and production_snapshot_digest are raw sha256 hex digests.
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
# Observation cohorts are free-form but must not be trivial placeholders.
_MIN_COMPAT_LEN = 8


def validate_artifact_schema_version(data: dict[str, Any]) -> str | None:
    """Require exact supported integer ``schema_version`` (no coercion).

    Returns an error string, or ``None`` when valid.
    """
    if "schema_version" not in data:
        return (
            "invalid artifact schema_version: missing "
            f"(supported: {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)})"
        )
    raw_sv = data["schema_version"]
    # type(x) is int rejects bool (subclass of int) and refuses str/float coercion.
    if type(raw_sv) is not int:
        return (
            f"invalid artifact schema_version: {raw_sv!r} "
            f"(must be integer in {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)}; "
            "no string/float coercion)"
        )
    if raw_sv not in SUPPORTED_ARTIFACT_SCHEMA_VERSIONS:
        return (
            f"unsupported artifact schema_version={raw_sv} "
            f"(supported: {sorted(SUPPORTED_ARTIFACT_SCHEMA_VERSIONS)})"
        )
    return None


def validate_production_identity_format(
    data: dict[str, Any],
    *,
    require_schema_version: bool = True,
) -> str | None:
    """Format/consistency checks only — not a claim of verified production authority.

    Does **not** prove the export digest exists in ``learning_policy_snapshots``.
    Callers that need verified authority must use
    :func:`validate_verified_production_identity` with a live DB connection.
    """
    if require_schema_version:
        schema_err = validate_artifact_schema_version(data)
        if schema_err is not None:
            return schema_err

    baseline_id = str(data.get("baseline_id") or "").strip().lower().replace("-", "_")
    if not baseline_id:
        return (
            "not eligible for verified production-policy promote: "
            "baseline_id is missing (required: production)"
        )
    if baseline_id != "production":
        return (
            "not eligible for verified production-policy promote: "
            f"baseline_id={baseline_id!r} (only baseline=production with verified "
            "snapshot/adapter identity is promote-eligible; static_reference digs "
            "remain human review only)"
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

    # Schema v3: population identity is material provenance for ACCUM promote.
    missing_pop = [
        k for k in _POPULATION_IDENTITY_V3 if k not in data or data[k] in (None, "")
    ]
    if missing_pop:
        return (
            "invalid challenge artifact schema v3: missing required population "
            f"identity fields: {', '.join(missing_pop)}"
        )
    pop_kind = str(data.get("population_identity_kind") or "").strip()
    pop_id = str(data.get("population_identity_id") or "").strip()
    pop_detail = data.get("population_identity_detail")
    if pop_kind != _ACCUM_POPULATION_KIND:
        return (
            "production identity invalid: population_identity_kind="
            f"{pop_kind!r} must be {_ACCUM_POPULATION_KIND!r} for verified "
            "production ACCUM promote reopen"
        )
    if pop_id != compat:
        return (
            "production identity invalid: population_identity_id="
            f"{pop_id!r} must equal observation_compatibility_id={compat!r}"
        )
    if not isinstance(pop_detail, dict) or not pop_detail:
        return (
            "production identity invalid: population_identity_detail must be a "
            "non-empty object (schema v3 material population identity)"
        )
    detail_kind = str(pop_detail.get("kind") or "").strip()
    if detail_kind and detail_kind != _ACCUM_POPULATION_KIND:
        return (
            "production identity invalid: population_identity_detail.kind="
            f"{detail_kind!r} must be {_ACCUM_POPULATION_KIND!r}"
        )
    detail_cid = str(
        pop_detail.get("compatibility_id") or pop_detail.get("population_id") or ""
    ).strip()
    if detail_cid and detail_cid != compat:
        return (
            "production identity invalid: population_identity_detail cohort "
            f"id={detail_cid!r} does not match observation_compatibility_id={compat!r}"
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


def validate_verified_production_identity(
    data: dict[str, Any],
    *,
    conn: sqlite3.Connection,
    require_schema_version: bool = True,
) -> str | None:
    """Verify production identity against authoritative ai-saham snapshots.

    Always requires a read-only DB connection. Format-only checks live in
    :func:`validate_production_identity_format` and must not be used alone for
    promote eligibility.
    """
    format_err = validate_production_identity_format(
        data, require_schema_version=require_schema_version
    )
    if format_err is not None:
        return format_err

    policy_id = str(data.get("policy_id") or "").strip()
    compat = str(data.get("observation_compatibility_id") or "").strip()
    snap_id = str(data.get("production_snapshot_id") or "").strip().lower()
    digest = str(data.get("production_snapshot_digest") or "").strip().lower()
    return verify_export_snapshot_against_db(
        conn,
        compatibility_id=compat,
        policy_id=policy_id,
        snapshot_id=snap_id,
        payload_digest=digest,
    )


def _after_presence_checks(
    data: dict[str, Any],
    *,
    conn: sqlite3.Connection,
) -> tuple[dict[str, Any] | None, str | None]:
    """Shared presence + schema + identity gate used by every reopen loader."""
    # Schema first: missing/wrong version must not be papered over by other fields.
    schema_err = validate_artifact_schema_version(data)
    if schema_err is not None:
        return None, schema_err
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
        data,
        conn=conn,
        require_schema_version=False,
    )
    if validity_err is not None:
        return None, validity_err
    return data, None


def load_evidence_json(
    path: Path,
    *,
    conn: sqlite3.Connection,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read JSON: {exc}"
    if not isinstance(data, dict):
        return None, "export root must be a JSON object"
    return _after_presence_checks(data, conn=conn)


def load_evidence_artifact(
    dir_path: Path,
    *,
    conn: sqlite3.Connection,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load from challenge artifact dir (manifest pack) or standalone export JSON.

    When ``manifest.json`` is present it is authoritative: ``export.json`` /
    ``result.json`` / ``champion.json`` cannot bypass manifest schema validation.
    Standalone export-shaped files are accepted only if no manifest is present,
    and still require the exact supported integer ``schema_version``.
    """
    if not dir_path.is_dir():
        return None, f"not a directory: {dir_path}"
    manifest_p = dir_path / "manifest.json"
    metrics_p = dir_path / "metrics.json"
    if manifest_p.is_file():
        try:
            manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
            metrics = (
                json.loads(metrics_p.read_text(encoding="utf-8"))
                if metrics_p.is_file()
                else {}
            )
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"cannot read artifact: {exc}"
        if not isinstance(manifest, dict):
            return None, "manifest.json root must be a JSON object"
        if metrics and not isinstance(metrics, dict):
            return None, "metrics.json root must be a JSON object"
        # Map challenge artifact layout; schema_version comes only from manifest.
        data = {
            "schema_version": manifest.get("schema_version"),
            "status": metrics.get("status") or manifest.get("status"),
            "policy_id": manifest.get("policy_id"),
            "protocol_id": manifest.get("protocol_id"),
            "policy_hash": manifest.get("policy_hash"),
            "baseline_id": manifest.get("baseline_id"),
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
        for key in _POPULATION_IDENTITY_V3:
            data[key] = manifest.get(key)
        weights_p = dir_path / "weights.json"
        if weights_p.is_file():
            try:
                data["weights"] = json.loads(weights_p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return _after_presence_checks(data, conn=conn)

    # No manifest: standalone export-shaped files only (strict schema required).
    for name in ("export.json", "result.json", "champion.json"):
        p = dir_path / name
        if p.is_file():
            return load_evidence_json(p, conn=conn)
    return None, "artifact dir missing manifest.json (or export.json)"


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
    db_path: Path | str | None = None,
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

    try:
        resolved_db = resolve_db_path(db_path)
    except Exception as exc:  # noqa: BLE001 — surface path resolution failures
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error=f"authoritative database path resolution failed: {exc}",
            lines=["BLOCKED: cannot resolve ai-saham database for identity verify"],
        )

    try:
        with aisaham_connect(resolved_db) as conn:
            if from_json is not None:
                evidence, err = load_evidence_json(Path(from_json), conn=conn)
            else:
                evidence, err = load_evidence_artifact(
                    Path(from_artifact),  # type: ignore[arg-type]
                    conn=conn,
                )
    except FileNotFoundError as exc:
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error=f"authoritative database missing: {exc}",
            lines=[
                "BLOCKED: ai-saham database required to verify production snapshots"
            ],
        )
    except OSError as exc:
        return PromotePacketResult(
            policy_id="",
            mode="tune",
            error=f"authoritative database unreadable: {exc}",
            lines=["BLOCKED: cannot open ai-saham database for identity verify"],
        )

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
            f"DB-verified: {resolved_db}",
        ],
        evidence=evidence,
    )
    if write_artifact:
        write_promote_packet(result, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
            result.lines.append(f"Open: {result.artifact_dir / 'PROMOTE.md'}")
    return result
