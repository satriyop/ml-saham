"""Write challenge run artifact packs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ml_saham.artifacts.writer import resolve_artifacts_root
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


def write_challenge_artifact(
    result: ChallengeResult,
    *,
    db_path: Path,
    artifacts_root: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    root = resolve_artifacts_root(artifacts_root)
    ts = datetime.now(tz=JAKARTA).strftime("%Y%m%d_%H%M%S")
    out = root / "challenge" / result.policy_id.replace("/", ".") / ts
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": 2,
        "mode": "challenge_run",
        "track": "policy_tournament",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "baseline_id": result.baseline_id,
        "against_id": result.against_id,
        "status": result.status.value,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
    }
    if extra:
        manifest["extra"] = extra

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    metrics = {
        "primary_ic_baseline": result.primary_ic_baseline,
        "primary_ic_against": result.primary_ic_against,
        "horizon_metrics": result.horizon_metrics,
        "fold_metrics": result.fold_metrics,
        "status": result.status.value,
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    (out / "weights.json").write_text(
        json.dumps(result.weights, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(result.summary_md or "", encoding="utf-8")
    result.artifact_dir = out
    return out


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
        "schema_version": 2,
        "mode": "challenge_factor",
        "track": "factor_validity",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
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
        root
        / "challenge"
        / "factor"
        / result.policy_id.replace("/", ".")
        / "_all"
        / ts
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
        "schema_version": 2,
        "mode": "challenge_factor_batch",
        "track": "factor_validity_batch",
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
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
        "schema_version": 2,
        "mode": "challenge_diagnostic",
        "track": "diagnostic_validity",
        "diagnostic_id": result.diagnostic_id,
        "protocol_id": result.protocol_id,
        "diagnostic_hash": result.diagnostic_hash,
        "feature": result.feature,
        "verdict": result.verdict.value,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "banner": "ADR-057: not Action authority",
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
    }
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
    manifest = {
        "schema_version": 2,
        "mode": "challenge_diagnostic_batch",
        "track": "diagnostic_validity_batch",
        "diagnostic_id": result.diagnostic_id,
        "protocol_id": result.protocol_id,
        "diagnostic_hash": result.diagnostic_hash,
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
        }
        for r in result.rows
    ]
    manifest = {
        "schema_version": 2,
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
        "schema_version": 2,
        "mode": "challenge_health",
        "engine_id": result.engine_id,
        "scenario_filter": result.scenario_filter,
        "with_champion": result.with_champion,
        "with_factors": result.with_factors,
        "db_path": str(db_path),
        "created_at": datetime.now(tz=JAKARTA).isoformat(),
        "n_index": len(result.index),
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
        "schema_version": 2,
        "mode": "challenge_promote_packet",
        "policy_id": result.policy_id,
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
