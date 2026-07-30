"""ADR-002 engine portfolios: PolicySpecs grouped by engine + scenario."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import write_engine_artifact
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.types import (
    ChallengeStatus,
    EnginePolicyRow,
    EnginePortfolioResult,
)

# engine_id → scenario → ordered policy_ids (ai-saham scenario wording)
ENGINE_POLICIES: dict[str, dict[str, list[str]]] = {
    "screener": {
        "accum": [
            "screener.accum.score_weights",
        ],
        "pre-open": [
            "screener.pre_open.iev_rank",
            "screener.pre_open.directional_score",
        ],
    },
    "signal": {
        "accum": [
            "signal.accum.raw_score",
        ],
    },
    "risk": {
        "accum": [
            "risk.accum.hard_gates",
        ],
    },
}

_SCENARIO_ALIASES: dict[str, str] = {
    "accum": "accum",
    "accumulation": "accum",
    "pre-open": "pre-open",
    "pre_open": "pre-open",
    "preopen": "pre-open",
    "pre open": "pre-open",
}


def list_engines() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for eng, scenarios in sorted(ENGINE_POLICIES.items()):
        out.append(
            {
                "engine_id": eng,
                "scenarios": sorted(scenarios.keys()),
                "n_policies": sum(len(v) for v in scenarios.values()),
                "policies": {
                    sc: list(pids) for sc, pids in sorted(scenarios.items())
                },
            }
        )
    return out


def normalize_scenario(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    key = str(raw).strip().lower().replace("_", "-")
    key = key.replace(" ", "-")
    # collapse double hyphens
    while "--" in key:
        key = key.replace("--", "-")
    # map preopen without hyphen
    if key in _SCENARIO_ALIASES:
        return _SCENARIO_ALIASES[key]
    # try underscore form already lowercased
    alt = raw.strip().lower().replace("-", "_")
    if alt in _SCENARIO_ALIASES:
        return _SCENARIO_ALIASES[alt]
    if key.replace("-", "") == "preopen":
        return "pre-open"
    return key


def resolve_engine_policies(
    engine_id: str,
    scenario: str | None = None,
) -> tuple[list[tuple[str, str]], str | None]:
    """Return ([(scenario, policy_id), ...], error_message_or_None)."""
    eng = engine_id.strip().lower()
    if eng not in ENGINE_POLICIES:
        known = ", ".join(sorted(ENGINE_POLICIES))
        return [], f"Unknown engine {engine_id!r}. Known: {known}"

    sc_map = ENGINE_POLICIES[eng]
    sc = normalize_scenario(scenario)
    if sc is None:
        pairs: list[tuple[str, str]] = []
        for sname in sorted(sc_map.keys()):
            for pid in sc_map[sname]:
                pairs.append((sname, pid))
        return pairs, None

    if sc not in sc_map:
        known = ", ".join(sorted(sc_map))
        return [], (
            f"Unknown scenario {scenario!r} for engine {eng!r}. "
            f"Known: {known}"
        )
    return [(sc, pid) for pid in sc_map[sc]], None


def _fmt_ic(x: float | None) -> str:
    return f"{x:+.4f}" if x is not None else "n/a"


def _short_notes(notes: list[str], n: int = 2) -> str:
    if not notes:
        return ""
    # prefer last notes (verdict / size)
    pick = notes[-n:] if len(notes) >= n else notes
    return "; ".join(pick)


def run_engine_portfolio(
    db_path: Path | str,
    engine_id: str,
    *,
    scenario: str | None = None,
    against: str = "equal_sleeves",
    baseline: str = "production",
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> EnginePortfolioResult:
    """Run all (or scenario-filtered) PolicySpecs; roll up English report."""
    path = Path(db_path)
    against = against.strip().lower().replace("-", "_")
    baseline = baseline.strip().lower().replace("-", "_") or "production"

    pairs, err = resolve_engine_policies(engine_id, scenario)
    if err:
        return EnginePortfolioResult(
            engine_id=engine_id.strip().lower(),
            scenario_filter=normalize_scenario(scenario),
            against_id=against,
            baseline_id=baseline,
            lines=[f"BLOCKED_POLICY: {err}"],
            summary_md=f"# Engine portfolio blocked\n\n{err}\n",
            notes=[err],
            resolve_error=err,
        )

    eng = engine_id.strip().lower()
    sc_filter = normalize_scenario(scenario)
    rows: list[EnginePolicyRow] = []
    global_notes: list[str] = []

    for sc_name, policy_id in pairs:
        try:
            result = run_policy_challenge(
                path,
                policy_id,
                against=against,
                baseline=baseline,
                write_artifact=False,
                artifacts_dir=None,
            )
            rows.append(
                EnginePolicyRow(
                    engine_id=eng,
                    scenario=sc_name,
                    policy_id=result.policy_id,
                    protocol_id=result.protocol_id,
                    policy_hash=result.policy_hash,
                    status=result.status.value,
                    n_rows=result.n_rows,
                    primary_horizon=result.primary_horizon,
                    primary_ic_baseline=result.primary_ic_baseline,
                    primary_ic_against=result.primary_ic_against,
                    against_id=result.against_id,
                    notes=list(result.notes),
                )
            )
        except Exception as exc:  # noqa: BLE001 — portfolio continues
            try:
                pol = load_policy(policy_id)
                phash = pol.hash
                proto = pol.protocol_id
            except Exception:
                phash = ""
                proto = ""
            rows.append(
                EnginePolicyRow(
                    engine_id=eng,
                    scenario=sc_name,
                    policy_id=policy_id,
                    protocol_id=proto,
                    policy_hash=phash,
                    status="ERROR",
                    n_rows=0,
                    primary_horizon=None,
                    primary_ic_baseline=None,
                    primary_ic_against=None,
                    against_id=against,
                    notes=[str(exc)],
                    error=str(exc),
                )
            )

    counts = Counter(r.status for r in rows)
    counts_dict = dict(counts)
    n_blocked = counts_dict.get(ChallengeStatus.BLOCKED_DATA.value, 0) + counts_dict.get(
        ChallengeStatus.BLOCKED_POLICY.value, 0
    )
    n_err = counts_dict.get("ERROR", 0)
    if n_blocked:
        global_notes.append(f"engine incomplete ({n_blocked} blocked policies)")
    if n_err:
        global_notes.append(f"{n_err} policy run(s) raised ERROR")
    runnable = [
        r
        for r in rows
        if r.status
        not in (
            ChallengeStatus.BLOCKED_DATA.value,
            ChallengeStatus.BLOCKED_POLICY.value,
            "ERROR",
        )
    ]
    if runnable and all(r.status == ChallengeStatus.LOSE.value for r in runnable):
        global_notes.append(f"no challenger wins under against={against}")

    sc_label = sc_filter or "all"
    lines = [
        "=== ENGINE PORTFOLIO (ADR-002) ===",
        f"Engine:    {eng}",
        f"Scenario:  {sc_label}",
        f"Against:   {against}   Baseline: {baseline}",
        f"Policies:  {len(rows)}   "
        + "  ".join(f"{k}={v}" for k, v in sorted(counts_dict.items())),
        "",
    ]
    # header
    lines.append(
        f"{'policy_id':<42} {'scen':<9} {'protocol':<22} {'status':<14} "
        f"{'n':>5} {'IC_prod':>9} {'IC_ag':>9}  notes"
    )
    lines.append("-" * 130)
    for r in rows:
        note = _short_notes(r.notes)
        if r.error:
            note = r.error[:60]
        lines.append(
            f"{r.policy_id:<42} {r.scenario:<9} {r.protocol_id:<22} {r.status:<14} "
            f"{r.n_rows:>5} {_fmt_ic(r.primary_ic_baseline):>9} "
            f"{_fmt_ic(r.primary_ic_against):>9}  {note}"
        )
    lines.append("")
    lines.append("Costs: gross · Not investment advice · Never auto-promotes ai-saham config")
    lines.append("Dig: ml-saham challenge run <policy_id> --against …")
    if global_notes:
        lines.append("")
        lines.append("Notes:")
        for n in global_notes:
            lines.append(f"  - {n}")

    md = [
        f"# Engine portfolio: {eng}",
        "",
        f"- **Scenario filter:** {sc_label}",
        f"- **Against:** {against}",
        f"- **Baseline:** {baseline}",
        f"- **Counts:** {counts_dict}",
        "",
        "## Policies",
        "",
        "| policy | scenario | protocol | status | n | IC_prod | IC_ag |",
        "|--------|----------|----------|--------|---|---------|-------|",
    ]
    for r in rows:
        md.append(
            f"| `{r.policy_id}` | {r.scenario} | {r.protocol_id} | {r.status} | "
            f"{r.n_rows} | {_fmt_ic(r.primary_ic_baseline)} | {_fmt_ic(r.primary_ic_against)} |"
        )
    md.extend(["", "## Notes", ""])
    for n in global_notes:
        md.append(f"- {n}")
    md.append("")
    md.append("Do **not** auto-promote. Dig with `challenge run <policy_id>`.")
    md.append("")

    result = EnginePortfolioResult(
        engine_id=eng,
        scenario_filter=sc_filter,
        against_id=against,
        baseline_id=baseline,
        rows=rows,
        counts=counts_dict,
        lines=lines,
        summary_md="\n".join(md),
        notes=global_notes,
    )
    if write_artifact:
        write_engine_artifact(result, db_path=path, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
    return result
