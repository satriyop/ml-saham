"""Write challenge run artifact packs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ml_saham.artifacts.writer import resolve_artifacts_root
from ml_saham.challenge.types import ChallengeResult

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
