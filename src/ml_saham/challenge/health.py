"""Challenge health report — control-tower recipe over existing runners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ml_saham.challenge.artifacts import (
    challenge_result_export_payload,
    write_health_artifact,
)
from ml_saham.challenge.diagnostic_validity import run_diagnostic_health
from ml_saham.challenge.engines import (
    normalize_scenario,
    resolve_engine_policies,
    run_engine_portfolio,
)
from ml_saham.challenge.factor_validity import run_factor_challenge_batch
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.challenge.readiness import build_accum_challenge_readiness
from ml_saham.challenge.production_policy_snapshots import (
    is_snapshot_contract_mismatch_note,
)
from ml_saham.challenge.types import ChallengeResult, HealthReportResult

ACCUM_POLICY = "screener.accum.score_weights"
DEFAULT_ENGINE = "screener"
DEFAULT_TUNE_AGAINST = "equal_sleeves"
DEFAULT_CHAMPION_MODEL = "lgbm_reweight"


def _fmt_ic(x: float | None) -> str:
    return f"{x:+.4f}" if x is not None else "n/a"


def _blocked_policy_contract_notes(engine_rows: list[dict[str, Any]]) -> list[str]:
    """Deduped BLOCKED notes that name a snapshot-contract disagreement."""
    seen: set[str] = set()
    notes: list[str] = []
    for row in engine_rows:
        if not str(row.get("status") or "").startswith("BLOCKED"):
            continue
        for note in row.get("notes") or []:
            if not is_snapshot_contract_mismatch_note(str(note)):
                continue
            if note in seen:
                continue
            seen.add(note)
            notes.append(note)
    return notes


def _engine_payload(eng) -> dict[str, Any]:
    return {
        "engine_id": eng.engine_id,
        "scenario_filter": eng.scenario_filter,
        "against_id": eng.against_id,
        "baseline_id": eng.baseline_id,
        "counts": eng.counts,
        "notes": eng.notes,
        "resolve_error": eng.resolve_error,
        "rows": [
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
            for r in eng.rows
        ],
    }


def _challenge_payload(result: ChallengeResult) -> dict[str, Any]:
    """Champion/tune export for health packs — same schema as CLI promote exports."""
    return challenge_result_export_payload(result)


def _factors_payload(batch) -> dict[str, Any]:
    return {
        "policy_id": batch.policy_id,
        "protocol_id": batch.protocol_id,
        "policy_hash": batch.policy_hash,
        "n_rows": batch.n_rows,
        "primary_horizon": batch.primary_horizon,
        "blocked": batch.blocked.value if batch.blocked else None,
        "notes": batch.notes,
        "observation_compatibility_id": batch.observation_compatibility_id,
        "production_snapshot_id": batch.production_snapshot_id,
        "production_snapshot_digest": batch.production_snapshot_digest,
        "production_policy_id": batch.production_policy_id,
        "production_policy_version": batch.production_policy_version,
        "production_semantic_engine_contract_id": (
            batch.production_semantic_engine_contract_id
        ),
        "challenge_adapter_id": batch.challenge_adapter_id,
        "challenge_adapter_version": batch.challenge_adapter_version,
        "factors": [
            {
                "factor": r.factor,
                "verdict": r.verdict.value,
                "mean_delta_ic": r.mean_delta_ic,
                "mean_univariate_ic": r.mean_univariate_ic,
                "fold_agree_positive_delta": r.fold_agree_positive_delta,
                "notes": r.notes[-3:],
            }
            for r in batch.results
        ],
    }


def _diagnostics_payload(batch) -> dict[str, Any]:
    """Separate display/promote-candidate section — never sleeve KEEP/DEMOTE."""
    return {
        "section": "diagnostics_display",
        "banner": "ADR-057: not Action authority — display / promote-candidate only",
        "diagnostic_id": batch.diagnostic_id,
        "protocol_id": batch.protocol_id,
        "n_rows": batch.n_rows,
        "primary_horizon": batch.primary_horizon,
        "blocked": batch.blocked.value if batch.blocked else None,
        "notes": batch.notes,
        "features": [
            {
                "feature": r.feature,
                "diagnostic_id": r.diagnostic_id,
                "verdict": r.verdict.value,
                "coverage": r.coverage,
                "mean_univariate_ic": r.mean_univariate_ic,
                "mean_residual_ic": r.mean_residual_ic,
                "mean_redundancy": r.mean_redundancy,
                "notes": r.notes[-2:],
            }
            for r in batch.results
        ],
    }


_PRODUCTION_IDENTITY_KEYS = (
    "observation_compatibility_id",
    "production_snapshot_id",
    "production_snapshot_digest",
    "production_policy_id",
    "production_policy_version",
    "production_semantic_engine_contract_id",
    "challenge_adapter_id",
    "challenge_adapter_version",
)


def _production_identities(
    engine_payload: dict[str, Any],
    champion_payload: dict[str, Any] | None,
    factors_payload: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Collect stable, deduplicated production bindings for the health manifest."""
    candidates = list(engine_payload.get("rows") or [])
    if champion_payload is not None:
        candidates.append(champion_payload)
    if factors_payload is not None:
        candidates.append(factors_payload)

    identities: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        values = tuple(
            str(candidate.get(key) or "") for key in _PRODUCTION_IDENTITY_KEYS
        )
        if not values[1] or values in seen:
            continue
        seen.add(values)
        identities.append(dict(zip(_PRODUCTION_IDENTITY_KEYS, values, strict=True)))
    return identities


def _attention(
    engine_rows: list[dict[str, Any]],
    champion: dict[str, Any] | None,
    factors: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None,
    notes: list[str],
) -> list[str]:
    attn: list[str] = []
    blocked = [r for r in engine_rows if str(r.get("status", "")).startswith("BLOCKED")]
    if blocked:
        attn.append(
            f"{len(blocked)} engine policy row(s) BLOCKED: "
            + ", ".join(r["policy_id"] for r in blocked[:5])
        )
        for note in _blocked_policy_contract_notes(blocked):
            attn.append(f"BLOCKED_POLICY: {note}")
    loses = [r for r in engine_rows if r.get("status") == "LOSE"]
    if loses:
        attn.append(
            f"{len(loses)} tune LOSE vs equal_sleeves: "
            + ", ".join(r["policy_id"] for r in loses[:5])
        )
    if champion:
        st = champion.get("status")
        if st == "WIN":
            attn.append(
                f"CHAMPION WIN: {champion.get('against_id')} beat production on "
                f"{champion.get('policy_id')} — human review only"
            )
        elif st and str(st).startswith("BLOCKED"):
            attn.append(
                f"champion {st}: {'; '.join((champion.get('notes') or [])[-2:])}"
            )
        elif st == "LOSE":
            attn.append("champion LOSE — production still ahead of learned scorer")
    if factors and not factors.get("blocked"):
        demote = [
            f["factor"]
            for f in factors.get("factors") or []
            if f.get("verdict") in ("DEMOTE", "DROP_CANDIDATE")
        ]
        if demote:
            attn.append("factor DEMOTE/DROP candidates: " + ", ".join(demote))
    if diagnostics and not diagnostics.get("blocked"):
        promo = [
            f["feature"]
            for f in diagnostics.get("features") or []
            if f.get("verdict") == "PROMOTE_CANDIDATE"
        ]
        drop = [
            f["feature"]
            for f in diagnostics.get("features") or []
            if f.get("verdict") in ("DROP_DISPLAY", "DEMOTE_DISPLAY")
        ]
        if promo:
            attn.append(
                "diagnostic PROMOTE_CANDIDATE (design tune PolicySpec; not Action): "
                + ", ".join(promo[:6])
            )
        if drop:
            attn.append(
                "diagnostic DEMOTE/DROP_DISPLAY (desk noise candidates): "
                + ", ".join(drop[:6])
            )
    for n in notes:
        if "skip" in n.lower():
            attn.append(n)
    if not attn:
        attn.append("No critical attention flags (still review table).")
    return attn


def build_summary_md(
    *,
    db_path: Path,
    scenario: str | None,
    with_champion: bool,
    with_factors: bool,
    with_diagnostics: bool,
    engine_payload: dict[str, Any],
    champion_payload: dict[str, Any] | None,
    factors_payload: dict[str, Any] | None,
    diagnostics_payload: dict[str, Any] | None,
    readiness_payload: dict[str, Any] | None,
    notes: list[str],
) -> str:
    sc = scenario or "all"
    lines = [
        "# Challenge health report",
        "",
        f"- **DB:** `{db_path}`",
        f"- **Engine:** screener · **scenario filter:** {sc}",
        f"- **Recipe:** engine tune (equal_sleeves)"
        f"{' + champion' if with_champion else ''}"
        f"{' + factors' if with_factors else ''}"
        f"{' + diagnostics' if with_diagnostics else ''}",
        "- **Disclaimer:** gross metrics · not investment advice · "
        "**never auto-promotes** ai-saham",
        "",
    ]
    if readiness_payload is not None:
        producer = readiness_payload["producer_handoff"]
        protocol = readiness_payload["protocol_readiness"]
        lines.extend(
            [
                "## ACCUM readiness (C0; no verdict)",
                "",
                "| axis | status | evidence |",
                "|---|---|---|",
                f"| producer handoff | {producer['status']} | "
                f"observations={producer['valid_observation_count']}/{producer['observation_count']}; "
                f"sessions={producer['session_count']}; snapshots="
                f"{producer['snapshot_verified_count']}/{producer['snapshot_required_count']} |",
                f"| Protocol | {protocol['status']} | panel={protocol['panel_rows']}; "
                f"sessions={protocol['panel_sessions']}; valid post-embargo folds="
                f"{protocol['estimated_valid_post_embargo_folds']}/"
                f"{protocol['min_folds_for_verdict']} |",
                "",
                "> Producer readiness and Protocol readiness are independent. "
                "Neither is WIN/LOSE or promotion authority.",
                "",
            ]
        )
    lines.extend(
        [
            "## Engine rollup (tune)",
            "",
            "| scenario | policy | status | n | IC_prod | IC_ag |",
            "|----------|--------|--------|---|---------|-------|",
        ]
    )
    for r in engine_payload.get("rows") or []:
        lines.append(
            f"| {r.get('scenario')} | `{r.get('policy_id')}` | {r.get('status')} | "
            f"{r.get('n_rows')} | {_fmt_ic(r.get('primary_ic_baseline'))} | "
            f"{_fmt_ic(r.get('primary_ic_against'))} |"
        )
    for note in _blocked_policy_contract_notes(engine_payload.get("rows") or []):
        lines.append("")
        lines.append(f"**BLOCKED_POLICY:** {note}")
    if engine_payload.get("resolve_error"):
        lines.append("")
        lines.append(f"**Engine resolve error:** {engine_payload['resolve_error']}")

    if with_champion:
        lines.extend(["", "## Champion", ""])
        if champion_payload is None:
            lines.append("_Champion skipped or not run._")
        else:
            lines.append(
                f"- **Policy:** `{champion_payload.get('policy_id')}` · "
                f"**against:** `{champion_payload.get('against_id')}`"
            )
            lines.append(f"- **Status:** {champion_payload.get('status')}")
            lines.append(
                f"- **IC:** production={_fmt_ic(champion_payload.get('primary_ic_baseline'))} · "
                f"champion={_fmt_ic(champion_payload.get('primary_ic_against'))}"
            )
            for n in (champion_payload.get("notes") or [])[-4:]:
                lines.append(f"- note: {n}")

    if with_factors:
        lines.extend(["", "## Factors (accum sleeves — KEEP/DEMOTE)", ""])
        if factors_payload is None:
            lines.append("_Factors skipped or not run._")
        elif factors_payload.get("blocked"):
            lines.append(f"**Blocked:** {factors_payload.get('blocked')}")
        else:
            lines.append("| factor | verdict | ΔIC | uni IC |")
            lines.append("|--------|---------|-----|--------|")
            for f in factors_payload.get("factors") or []:
                lines.append(
                    f"| {f.get('factor')} | {f.get('verdict')} | "
                    f"{_fmt_ic(f.get('mean_delta_ic'))} | "
                    f"{_fmt_ic(f.get('mean_univariate_ic'))} |"
                )

    if with_diagnostics:
        lines.extend(
            [
                "",
                "## Diagnostics (display bags — not Action authority)",
                "",
                "> ADR-057: KEEP_DISPLAY / DEMOTE_DISPLAY / PROMOTE_CANDIDATE only. "
                "**Not** sleeve KEEP/DEMOTE. **Never** sets TradeSetup Action.",
                "",
            ]
        )
        if diagnostics_payload is None:
            lines.append("_Diagnostics skipped or not run._")
        elif diagnostics_payload.get("blocked"):
            lines.append(f"**Blocked:** {diagnostics_payload.get('blocked')}")
        else:
            lines.append("| bag:feature | verdict | coverage | residual IC |")
            lines.append("|-------------|---------|----------|-------------|")
            for f in diagnostics_payload.get("features") or []:
                cov = f.get("coverage")
                cov_s = f"{cov:.0%}" if isinstance(cov, (int, float)) else "n/a"
                lines.append(
                    f"| {f.get('feature')} | {f.get('verdict')} | {cov_s} | "
                    f"{_fmt_ic(f.get('mean_residual_ic'))} |"
                )

    attn = _attention(
        list(engine_payload.get("rows") or []),
        champion_payload,
        factors_payload,
        diagnostics_payload,
        notes,
    )
    lines.extend(["", "## Attention", ""])
    for a in attn:
        lines.append(f"- {a}")

    lines.extend(
        [
            "",
            "## Next digs",
            "",
            "```bash",
            "# Replace <ACCUM_COHORT_ID> with the exact ACCUM observation compatibility_id",
            "# (production-facing ACCUM/PRE_OPEN commands fail closed without it).",
            "# 1 catalog",
            "ml-saham challenge list",
            "# 2 weekly tower (default)",
            "ml-saham challenge health --with-diagnostics "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "# 3 dig only when retuning signal/risk/screener knobs",
            "ml-saham challenge engine signal --scenario accum "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge engine risk --scenario accum --against gate_off "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge run screener.accum.score_weights --against equal_sleeves "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge run signal.accum.raw_score --against equal_sleeves "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge run risk.accum.hard_gates --against gate_off "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge factor screener.accum.score_weights --all "
            "--compatibility-id <ACCUM_COHORT_ID>",
            "ml-saham challenge champion screener.accum.score_weights "
            "--model lgbm_reweight --compatibility-id <ACCUM_COHORT_ID>",
            "# diagnostics: PROMOTE_CANDIDATE → PolicySpec design (never Action/ENTER)",
            "ml-saham challenge diagnostic list",
            "ml-saham challenge promote-packet --from-json <export.json>",
            "```",
            "",
            "## Never auto-promote / never Action from diagnostics",
            "",
            "This pack is **decision support only**. Do not write ai-saham configs from ml-saham.",
            "Diagnostic verdicts never set TradeSetup Action. P4 ENTER is deferred "
            "(needs dense Action labels + real ENTER H0 — not more rank IC).",
            "",
        ]
    )
    return "\n".join(lines)


def build_health_report(
    db_path: Path | str,
    *,
    engine_id: str = DEFAULT_ENGINE,
    scenario: str | None = None,
    with_champion: bool = False,
    with_factors: bool = False,
    with_diagnostics: bool = False,
    champion_model: str = DEFAULT_CHAMPION_MODEL,
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
    compatibility_id: str | None = None,
    diagnostic_compatibility_ids: dict[str, str] | None = None,
) -> HealthReportResult:
    """Run health recipe; always prefer honest BLOCKED over crash.

    ``compatibility_id`` is forwarded to child runners. Each production-facing
    policy validates its own purpose-family population identity (ACCUM vs
    PRE_OPEN vs IEV batch) — health does not treat one id as universal
    verified provenance.
    """
    path = Path(db_path)
    notes: list[str] = []
    sc = normalize_scenario(scenario)

    # Validate scenario early via resolve (engine still runs and may error too)
    _pairs, resolve_err = resolve_engine_policies(engine_id, sc)
    if resolve_err:
        return HealthReportResult(
            engine_id=engine_id,
            scenario_filter=sc,
            with_champion=with_champion,
            with_factors=with_factors,
            with_diagnostics=with_diagnostics,
            summary_md=f"# Health blocked\n\n{resolve_err}\n",
            lines=[f"BLOCKED_POLICY: {resolve_err}"],
            notes=[resolve_err],
            resolve_error=resolve_err,
        )

    if not path.is_file():
        err = f"DB file not found: {path}"
        return HealthReportResult(
            engine_id=engine_id,
            scenario_filter=sc,
            with_champion=with_champion,
            with_factors=with_factors,
            with_diagnostics=with_diagnostics,
            summary_md=f"# Health blocked\n\n{err}\n",
            lines=[f"BLOCKED_DATA: {err}"],
            notes=[err],
            resolve_error=err,
        )

    eng = run_engine_portfolio(
        path,
        engine_id,
        scenario=sc,
        against=DEFAULT_TUNE_AGAINST,
        write_artifact=False,
        artifacts_dir=None,
        compatibility_id=compatibility_id,
    )
    engine_payload = _engine_payload(eng)
    notes.extend(eng.notes)

    champion_payload: dict[str, Any] | None = None
    if with_champion:
        # Champion requires accum policy; skip if scenario excludes accum
        pairs, _ = resolve_engine_policies(engine_id, sc)
        has_accum = any(pid == ACCUM_POLICY for _, pid in pairs)
        if not has_accum:
            notes.append(
                "skip champion: requires accum policy "
                f"({ACCUM_POLICY}); scenario filter excluded it"
            )
        else:
            ch = run_policy_challenge(
                path,
                ACCUM_POLICY,
                against=champion_model,
                write_artifact=False,
                artifacts_dir=None,
                compatibility_id=compatibility_id,
            )
            champion_payload = _challenge_payload(ch)

    factors_payload: dict[str, Any] | None = None
    if with_factors:
        # Factors always target accum policy (document in notes)
        notes.append(
            f"factors always target {ACCUM_POLICY} (independent of scenario filter)"
        )
        batch = run_factor_challenge_batch(
            path,
            ACCUM_POLICY,
            write_artifact=False,
            artifacts_dir=None,
            compatibility_id=compatibility_id,
        )
        factors_payload = _factors_payload(batch)

    diagnostics_payload: dict[str, Any] | None = None
    if with_diagnostics:
        # Display bags for accum by default; pre-open-only filter still runs accum bags
        # (diagnostic registry is scenario-tagged; filter maps to accum when mixed/all).
        diag_sc = sc if sc in ("accum", "pre-open") else "accum"
        if diag_sc == "pre-open":
            notes.append(
                "diagnostics slice: no pre-open DiagnosticSpecs yet; "
                "running scenario=accum display bags"
            )
            diag_sc = "accum"
        notes.append(
            f"diagnostics = display bags (ADR-057); not sleeve KEEP/DEMOTE; "
            f"scenario={diag_sc}"
        )
        dbatch = run_diagnostic_health(
            path,
            scenario=diag_sc,
            write_artifact=False,
            artifacts_dir=None,
            compatibility_id=compatibility_id,
            diagnostic_compatibility_ids=diagnostic_compatibility_ids,
        )
        diagnostics_payload = _diagnostics_payload(dbatch)

    readiness_payload: dict[str, Any] | None = None
    pairs, _ = resolve_engine_policies(engine_id, sc)
    if any(pid == ACCUM_POLICY for _, pid in pairs):
        readiness_payload = build_accum_challenge_readiness(
            path,
            compatibility_id=compatibility_id,
            policy_id=ACCUM_POLICY,
        ).to_dict()

    summary_md = build_summary_md(
        db_path=path.resolve(),
        scenario=sc,
        with_champion=with_champion,
        with_factors=with_factors,
        with_diagnostics=with_diagnostics,
        engine_payload=engine_payload,
        champion_payload=champion_payload,
        factors_payload=factors_payload,
        diagnostics_payload=diagnostics_payload,
        readiness_payload=readiness_payload,
        notes=notes,
    )

    index: list[dict[str, Any]] = []
    for r in engine_payload.get("rows") or []:
        index.append(
            {
                "section": "engine",
                "policy_id": r.get("policy_id"),
                "status": r.get("status"),
                "against_id": r.get("against_id"),
            }
        )
    if champion_payload:
        index.append(
            {
                "section": "champion",
                "policy_id": champion_payload.get("policy_id"),
                "status": champion_payload.get("status"),
                "against_id": champion_payload.get("against_id"),
            }
        )
    if factors_payload and not factors_payload.get("blocked"):
        for f in factors_payload.get("factors") or []:
            index.append(
                {
                    "section": "factor",
                    "policy_id": factors_payload.get("policy_id"),
                    "factor": f.get("factor"),
                    "status": f.get("verdict"),
                }
            )
    if diagnostics_payload and not diagnostics_payload.get("blocked"):
        for f in diagnostics_payload.get("features") or []:
            index.append(
                {
                    "section": "diagnostic_display",
                    "diagnostic_id": f.get("diagnostic_id"),
                    "feature": f.get("feature"),
                    "status": f.get("verdict"),
                }
            )

    lines = [
        "=== CHALLENGE HEALTH (control tower) ===",
        f"DB: {path}",
        f"Scenario: {sc or 'all'} · champion={with_champion} · "
        f"factors={with_factors} · diagnostics={with_diagnostics}",
        "",
    ]
    lines.extend(summary_md.splitlines()[:50])
    if len(summary_md.splitlines()) > 50:
        lines.append("… (full summary in artifact summary.md)")

    result = HealthReportResult(
        engine_id=engine_id,
        scenario_filter=sc,
        with_champion=with_champion,
        with_factors=with_factors,
        with_diagnostics=with_diagnostics,
        summary_md=summary_md,
        lines=lines,
        notes=notes,
        index=index,
        engine_payload=engine_payload,
        champion_payload=champion_payload,
        factors_payload=factors_payload,
        diagnostics_payload=diagnostics_payload,
        readiness_payload=readiness_payload,
        production_identities=_production_identities(
            engine_payload, champion_payload, factors_payload
        ),
    )
    if write_artifact:
        write_health_artifact(result, db_path=path, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
    return result
