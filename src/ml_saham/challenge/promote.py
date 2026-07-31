"""Promote packet — human review checklist from challenge exports (no auto-apply)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import write_promote_packet
from ml_saham.challenge.champion import is_champion_against
from ml_saham.challenge.types import PromotePacketResult

_REQUIRED = (
    "status",
    "policy_id",
    "protocol_id",
    "baseline_id",
    "against_id",
)


def load_evidence_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read JSON: {exc}"
    if not isinstance(data, dict):
        return None, "export root must be a JSON object"
    missing = [k for k in _REQUIRED if k not in data or data[k] in (None, "")]
    if missing:
        return None, f"missing required fields: {', '.join(missing)}"
    return data, None


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
    # Map challenge artifact layout
    data = {
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
    weights_p = dir_path / "weights.json"
    if weights_p.is_file():
        try:
            data["weights"] = json.loads(weights_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    missing = [k for k in _REQUIRED if not data.get(k)]
    if missing:
        return None, f"artifact incomplete, missing: {', '.join(missing)}"
    return data, None


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
