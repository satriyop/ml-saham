"""Factor validity track: univariate IC + drop ablation → KEEP/DEMOTE/DROP_CANDIDATE."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from ml_saham.challenge.artifacts import write_batch_factor_artifact, write_factor_artifact
from ml_saham.challenge.metrics import Fold, ic_safe, time_purged_folds
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.protocols import ACCUM_PATH_V1, get_protocol
from ml_saham.challenge.runner import _horizon_ics, _select_rows, prepare_accum_panel
from ml_saham.challenge.scorers import score_production, score_production_drop
from ml_saham.challenge.types import (
    BatchFactorResult,
    ChallengeStatus,
    FactorChallengeResult,
    FactorVerdict,
    PolicySnapshot,
    Protocol,
)


def resolve_factor_key(policy: PolicySnapshot, raw: str) -> str | None:
    """Map alias or key → canonical enabled component key; None if invalid."""
    needle = raw.strip().lower().replace("-", "_")
    for c in policy.enabled_components():
        if c.key.lower() == needle or needle in {a.lower() for a in c.aliases}:
            return c.key
    return None


def list_enabled_factors(policy_id: str = "screener.accum.score_weights") -> list[dict[str, object]]:
    pol = load_policy(policy_id)
    return [
        {"key": c.key, "weight": c.weight, "aliases": list(c.aliases)}
        for c in pol.enabled_components()
    ]


def _univariate_ics(
    rows: Sequence[PanelRow],
    factor: str,
    horizons: tuple[int, ...],
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for h in horizons:
        xs: list[float] = []
        ys: list[float] = []
        for r in rows:
            if h not in r.excess:
                continue
            xs.append(r.components.get(factor, 0.0))
            ys.append(r.excess[h])
        if len(xs) < 5 or float(np.std(xs)) < 1e-12:
            out[str(h)] = None
        else:
            out[str(h)] = ic_safe(xs, ys)
    return out


def _factor_verdict(
    protocol: Protocol,
    fold_metrics: list[dict],
    *,
    mean_delta: float | None,
    mean_u: float | None,
) -> tuple[FactorVerdict, list[str]]:
    notes: list[str] = []
    eps = protocol.win_margin
    valid = [f for f in fold_metrics if f.get("delta_ic") is not None]
    if not valid or mean_delta is None:
        return FactorVerdict.INCONCLUSIVE, ["no valid fold delta_ic"]

    agree = sum(1 for f in valid if float(f["delta_ic"]) > 0) / len(valid)
    u = mean_u if mean_u is not None else 0.0
    abs_u = abs(u)

    if mean_delta >= eps and agree >= protocol.min_fold_agree:
        return FactorVerdict.KEEP, notes

    if mean_delta <= 0 and abs_u < eps:
        notes.append("removing factor does not hurt; univariate weak")
        return FactorVerdict.DROP_CANDIDATE, notes

    if mean_delta <= eps * 0.5 and abs_u < eps and agree <= 0.5:
        notes.append("ablation ~neutral and weak univariate IC")
        return FactorVerdict.DROP_CANDIDATE, notes

    if 0 < mean_delta < eps or (abs_u < eps and mean_delta > 0):
        notes.append("weak or unstable contribution")
        return FactorVerdict.DEMOTE, notes

    if abs_u >= eps and abs(mean_delta) < eps:
        notes.append("univariate signal but little marginal ablation (possible redundancy)")
        return FactorVerdict.DEMOTE, notes

    if agree < protocol.min_fold_agree:
        notes.append(f"fold agree on positive delta={agree:.0%}")
        return FactorVerdict.INCONCLUSIVE, notes

    return FactorVerdict.INCONCLUSIVE, notes + ["conflicting univariate vs ablation"]


def _status_to_factor_blocked(st: ChallengeStatus) -> FactorVerdict:
    if st == ChallengeStatus.BLOCKED_POLICY:
        return FactorVerdict.BLOCKED_POLICY
    return FactorVerdict.BLOCKED_DATA


def run_factor_challenge(
    db_path: Path | str,
    policy_id: str = "screener.accum.score_weights",
    *,
    factor: str,
    protocol_id: str = "accum_path_v1",
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> FactorChallengeResult:
    path = Path(db_path)
    factor_raw = factor.strip()

    try:
        policy_probe = load_policy(policy_id)
        get_protocol(protocol_id)
    except KeyError as exc:
        return FactorChallengeResult(
            verdict=FactorVerdict.BLOCKED_POLICY,
            policy_id=policy_id,
            protocol_id=protocol_id,
            policy_hash="",
            factor=factor_raw,
            n_rows=0,
            primary_horizon=ACCUM_PATH_V1.primary_horizon,
            lines=[f"BLOCKED_POLICY: {exc}"],
            summary_md=f"# Factor challenge blocked\n\n{exc}\n",
            notes=[str(exc)],
        )

    canon = resolve_factor_key(policy_probe, factor_raw)
    if canon is None:
        all_by = {c.key.lower(): c for c in policy_probe.components}
        for c in policy_probe.components:
            for a in c.aliases:
                all_by[a.lower()] = c
        hit = all_by.get(factor_raw.lower().replace("-", "_"))
        if hit is not None and (not hit.enabled or hit.weight <= 0):
            msg = (
                f"factor {factor_raw!r} is disabled / weight 0 in production snapshot "
                f"(v1 challenges enabled sleeves only)"
            )
        else:
            enabled = ", ".join(c.key for c in policy_probe.enabled_components())
            msg = f"unknown or non-enabled factor {factor_raw!r}. Enabled: {enabled}"
        return FactorChallengeResult(
            verdict=FactorVerdict.BLOCKED_POLICY,
            policy_id=policy_probe.policy_id,
            protocol_id=protocol_id,
            policy_hash=policy_probe.hash,
            factor=factor_raw,
            n_rows=0,
            primary_horizon=ACCUM_PATH_V1.primary_horizon,
            lines=["BLOCKED_POLICY:", f"  - {msg}"],
            summary_md=f"# Factor challenge BLOCKED_POLICY\n\n{msg}\n",
            notes=[msg],
        )

    prep = prepare_accum_panel(path, policy_id, protocol_id)
    if prep.blocked is not None or prep.policy is None or prep.protocol is None:
        blocked = _status_to_factor_blocked(prep.blocked or ChallengeStatus.BLOCKED_DATA)
        return FactorChallengeResult(
            verdict=blocked,
            policy_id=policy_id if prep.policy is None else prep.policy.policy_id,
            protocol_id=protocol_id if prep.protocol is None else prep.protocol.protocol_id,
            policy_hash="" if prep.policy is None else prep.policy.hash,
            factor=canon,
            n_rows=len(prep.rows),
            primary_horizon=(
                ACCUM_PATH_V1.primary_horizon
                if prep.protocol is None
                else prep.protocol.primary_horizon
            ),
            lines=[f"{blocked.value}:"] + [f"  - {n}" for n in prep.notes],
            summary_md=f"# Factor challenge {blocked.value}\n\n"
            + "\n".join(f"- {n}" for n in prep.notes)
            + "\n",
            notes=prep.notes,
        )

    policy = prep.policy
    protocol = prep.protocol
    rows = prep.rows
    notes = list(prep.notes)

    folds = time_purged_folds(rows, protocol)
    if not folds:
        return FactorChallengeResult(
            verdict=FactorVerdict.BLOCKED_DATA,
            policy_id=policy.policy_id,
            protocol_id=protocol.protocol_id,
            policy_hash=policy.hash,
            factor=canon,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon,
            lines=["BLOCKED_DATA: could not form time folds"],
            notes=notes + ["no folds"],
        )

    result = _score_factor_on_folds(
        policy=policy,
        protocol=protocol,
        rows=rows,
        folds=folds,
        factor=canon,
        prep_notes=notes,
        full_scores_by_fold=None,
    )
    if write_artifact:
        write_factor_artifact(result, db_path=path, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
    return result


def _score_factor_on_folds(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    rows: Sequence[PanelRow],
    folds: Sequence[Fold],
    factor: str,
    prep_notes: list[str],
    full_scores_by_fold: dict[int, list[float]] | None,
) -> FactorChallengeResult:
    """Score one factor given shared panel + folds. Optionally reuse full production scores."""
    notes = list(prep_notes)
    fold_metrics: list[dict] = []
    oos_full: list[float] = []
    oos_drop: list[float] = []
    oos_rows: list[PanelRow] = []
    oos_factor_vals: list[float] = []

    for fi, fold in enumerate(folds):
        test = _select_rows(rows, fold.test_idx)
        if full_scores_by_fold is not None and fi in full_scores_by_fold:
            full_s = full_scores_by_fold[fi]
        else:
            full_s = score_production(test, policy)
        try:
            drop_s = score_production_drop(test, policy, factor)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"scorer error on fold {fi}: {exc}")
            fold_metrics.append(
                {
                    "fold": fi,
                    "n_test": len(test),
                    "ic_full": None,
                    "ic_drop": None,
                    "delta_ic": None,
                    "univariate_ic": None,
                    "date_min": test[0].date if test else None,
                    "date_max": test[-1].date if test else None,
                }
            )
            continue

        y = [r.excess[protocol.primary_horizon] for r in test]
        ic_full = ic_safe(full_s, y)
        ic_drop = ic_safe(drop_s, y)
        fx = [r.components.get(factor, 0.0) for r in test]
        u_ic = ic_safe(fx, y) if len(fx) >= 5 and float(np.std(fx)) >= 1e-12 else None
        delta = None
        if ic_full is not None and ic_drop is not None:
            delta = float(ic_full) - float(ic_drop)
        fold_metrics.append(
            {
                "fold": fi,
                "n_test": len(test),
                "ic_full": ic_full,
                "ic_drop": ic_drop,
                "delta_ic": delta,
                "univariate_ic": u_ic,
                "date_min": test[0].date if test else None,
                "date_max": test[-1].date if test else None,
            }
        )
        oos_full.extend(full_s)
        oos_drop.extend(drop_s)
        oos_rows.extend(test)
        oos_factor_vals.extend(fx)

    deltas = [float(f["delta_ic"]) for f in fold_metrics if f.get("delta_ic") is not None]
    us = [float(f["univariate_ic"]) for f in fold_metrics if f.get("univariate_ic") is not None]
    mean_delta = sum(deltas) / len(deltas) if deltas else None
    mean_u = sum(us) / len(us) if us else None
    agree = sum(1 for d in deltas if d > 0) / len(deltas) if deltas else None

    zero_frac = sum(1 for v in oos_factor_vals if abs(v) < 1e-12) / max(len(oos_factor_vals), 1)
    if zero_frac > 0.8:
        notes.append(f"factor mostly zero on OOS rows ({zero_frac:.0%})")

    verdict, vnotes = _factor_verdict(
        protocol, fold_metrics, mean_delta=mean_delta, mean_u=mean_u
    )
    notes.extend(vnotes)

    horizon_metrics = {
        "full": _horizon_ics(oos_rows, oos_full, protocol.horizons_report)
        if oos_rows
        else {},
        "drop": _horizon_ics(oos_rows, oos_drop, protocol.horizons_report) if oos_rows else {},
        "univariate": _univariate_ics(oos_rows, factor, protocol.horizons_report)
        if oos_rows
        else {},
    }

    lines = _format_factor_lines(
        policy=policy,
        protocol=protocol,
        factor=factor,
        verdict=verdict,
        n_rows=len(rows),
        mean_delta=mean_delta,
        mean_u=mean_u,
        agree=agree,
        horizon_metrics=horizon_metrics,
        fold_metrics=fold_metrics,
        notes=notes,
    )
    summary = _format_factor_summary(
        policy=policy,
        protocol=protocol,
        factor=factor,
        verdict=verdict,
        mean_delta=mean_delta,
        mean_u=mean_u,
        horizon_metrics=horizon_metrics,
        notes=notes,
    )

    return FactorChallengeResult(
        verdict=verdict,
        policy_id=policy.policy_id,
        protocol_id=protocol.protocol_id,
        policy_hash=policy.hash,
        factor=factor,
        n_rows=len(rows),
        primary_horizon=protocol.primary_horizon,
        mean_delta_ic=mean_delta,
        mean_univariate_ic=mean_u,
        fold_agree_positive_delta=agree,
        horizon_metrics=horizon_metrics,
        fold_metrics=fold_metrics,
        lines=lines,
        summary_md=summary,
        notes=notes,
    )


def run_factor_challenge_batch(
    db_path: Path | str,
    policy_id: str = "screener.accum.score_weights",
    *,
    protocol_id: str = "accum_path_v1",
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> BatchFactorResult:
    """Run validity for every enabled sleeve; prep panel/folds once."""
    path = Path(db_path)
    prep = prepare_accum_panel(path, policy_id, protocol_id)
    if prep.blocked is not None or prep.policy is None or prep.protocol is None:
        blocked = _status_to_factor_blocked(prep.blocked or ChallengeStatus.BLOCKED_DATA)
        lines = [
            "=== FACTOR VALIDITY BATCH (ADR-002) ===",
            f"Policy: {policy_id}",
            f"Status: {blocked.value}",
            "",
            *[f"  - {n}" for n in prep.notes],
        ]
        return BatchFactorResult(
            policy_id=policy_id if prep.policy is None else prep.policy.policy_id,
            protocol_id=protocol_id if prep.protocol is None else prep.protocol.protocol_id,
            policy_hash="" if prep.policy is None else prep.policy.hash,
            n_rows=len(prep.rows),
            primary_horizon=(
                ACCUM_PATH_V1.primary_horizon
                if prep.protocol is None
                else prep.protocol.primary_horizon
            ),
            results=[],
            blocked=blocked,
            lines=lines,
            summary_md=f"# Factor batch {blocked.value}\n\n"
            + "\n".join(f"- {n}" for n in prep.notes)
            + "\n",
            notes=prep.notes,
        )

    policy = prep.policy
    protocol = prep.protocol
    rows = prep.rows
    notes = list(prep.notes)
    enabled = list(policy.enabled_components())
    if not enabled:
        msg = "no enabled sleeves on policy"
        return BatchFactorResult(
            policy_id=policy.policy_id,
            protocol_id=protocol.protocol_id,
            policy_hash=policy.hash,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon,
            results=[],
            blocked=FactorVerdict.BLOCKED_POLICY,
            lines=["BLOCKED_POLICY:", f"  - {msg}"],
            summary_md=f"# Factor batch BLOCKED_POLICY\n\n{msg}\n",
            notes=notes + [msg],
        )

    folds = time_purged_folds(rows, protocol)
    if not folds:
        msg = "could not form time folds"
        return BatchFactorResult(
            policy_id=policy.policy_id,
            protocol_id=protocol.protocol_id,
            policy_hash=policy.hash,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon,
            results=[],
            blocked=FactorVerdict.BLOCKED_DATA,
            lines=["BLOCKED_DATA:", f"  - {msg}"],
            summary_md=f"# Factor batch BLOCKED_DATA\n\n{msg}\n",
            notes=notes + [msg],
        )

    # Cache full production scores once per fold
    full_scores_by_fold: dict[int, list[float]] = {}
    for fi, fold in enumerate(folds):
        test = _select_rows(rows, fold.test_idx)
        full_scores_by_fold[fi] = score_production(test, policy)

    results: list[FactorChallengeResult] = []
    for comp in enabled:
        try:
            fr = _score_factor_on_folds(
                policy=policy,
                protocol=protocol,
                rows=rows,
                folds=folds,
                factor=comp.key,
                prep_notes=notes,
                full_scores_by_fold=full_scores_by_fold,
            )
        except Exception as exc:  # noqa: BLE001
            fr = FactorChallengeResult(
                verdict=FactorVerdict.INCONCLUSIVE,
                policy_id=policy.policy_id,
                protocol_id=protocol.protocol_id,
                policy_hash=policy.hash,
                factor=comp.key,
                n_rows=len(rows),
                primary_horizon=protocol.primary_horizon,
                notes=[f"batch scorer error: {exc}"],
                lines=[f"INCONCLUSIVE {comp.key}: {exc}"],
                summary_md=f"# {comp.key}\n\nError: {exc}\n",
            )
        results.append(fr)

    lines, summary_md = _format_batch_report(
        policy=policy,
        protocol=protocol,
        n_rows=len(rows),
        n_folds=len(folds),
        results=results,
        notes=notes,
        weight_by_key={c.key: c.weight for c in enabled},
    )
    batch = BatchFactorResult(
        policy_id=policy.policy_id,
        protocol_id=protocol.protocol_id,
        policy_hash=policy.hash,
        n_rows=len(rows),
        primary_horizon=protocol.primary_horizon,
        results=results,
        blocked=None,
        lines=lines,
        summary_md=summary_md,
        notes=notes,
    )
    if write_artifact:
        write_batch_factor_artifact(batch, db_path=path, artifacts_root=artifacts_dir)
        if batch.artifact_dir:
            batch.lines.append(f"Artifact: {batch.artifact_dir}")
    return batch


def _format_batch_report(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    n_rows: int,
    n_folds: int,
    results: list[FactorChallengeResult],
    notes: list[str],
    weight_by_key: dict[str, float],
) -> tuple[list[str], str]:
    def fmt(x: float | None) -> str:
        return f"{x:+.4f}" if x is not None else "n/a"

    lines = [
        "=== FACTOR VALIDITY BATCH (ADR-002) ===",
        f"Policy:   {policy.policy_id}  hash={policy.hash}",
        f"Protocol: {protocol.protocol_id}  primary_H={protocol.primary_horizon}  "
        f"report_H={list(protocol.horizons_report)}",
        "Methods:  univariate IC + drop ablation (shared panel)",
        f"Panel n:  {n_rows}   Folds: {n_folds}   Factors: {len(results)}",
        "",
        f"{'factor':<22} {'w':>6} {'univ@H':>9} {'dIC':>9} {'agree':>7}  verdict",
        "-" * 72,
    ]
    md = [
        f"# Factor validity batch — {policy.policy_id}",
        "",
        f"- Protocol: `{protocol.protocol_id}` primary H={protocol.primary_horizon}",
        f"- Panel n={n_rows}, folds={n_folds}",
        "",
        "| factor | weight | univ_IC@H | ΔIC | agreeΔ>0 | verdict |",
        "|--------|--------|-----------|-----|----------|---------|",
    ]
    for r in results:
        w = weight_by_key.get(r.factor, 0.0)
        agree_s = (
            f"{r.fold_agree_positive_delta:.0%}"
            if r.fold_agree_positive_delta is not None
            else "n/a"
        )
        lines.append(
            f"{r.factor:<22} {w:6.1f} {fmt(r.mean_univariate_ic):>9} "
            f"{fmt(r.mean_delta_ic):>9} {agree_s:>7}  {r.verdict.value}"
        )
        md.append(
            f"| {r.factor} | {w:.1f} | {fmt(r.mean_univariate_ic)} | "
            f"{fmt(r.mean_delta_ic)} | {agree_s} | {r.verdict.value} |"
        )

    lines.append("")
    lines.append("Dig in: ml-saham challenge factor POLICY --factor KEY")
    lines.append("Costs: gross · Not investment advice · Never auto-promotes ai-saham config.")
    non_keep = [r for r in results if r.verdict != FactorVerdict.KEEP]
    if non_keep:
        lines.append("")
        lines.append("Non-KEEP notes:")
        for r in non_keep:
            tip = r.notes[-1] if r.notes else r.verdict.value
            lines.append(f"  - {r.factor}: {r.verdict.value} — {tip}")
    if notes:
        lines.append("")
        lines.append("Prep notes:")
        for n in notes[:8]:
            lines.append(f"  - {n}")

    md.extend(["", "## Non-KEEP", ""])
    for r in non_keep:
        tip = r.notes[-1] if r.notes else ""
        md.append(f"- **{r.factor}** ({r.verdict.value}): {tip}")
    md.append("")
    md.append("Do **not** auto-edit ai-saham. Re-run with `--factor` for fold detail.")
    md.append("")
    return lines, "\n".join(md)


def _format_factor_lines(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    factor: str,
    verdict: FactorVerdict,
    n_rows: int,
    mean_delta: float | None,
    mean_u: float | None,
    agree: float | None,
    horizon_metrics: dict,
    fold_metrics: list[dict],
    notes: list[str],
) -> list[str]:
    def fmt(x: float | None) -> str:
        return f"{x:+.4f}" if x is not None else "n/a"

    agree_s = f"{agree:.0%}" if agree is not None else "n/a"
    lines = [
        "=== FACTOR VALIDITY (ADR-002) ===",
        f"Policy:   {policy.policy_id}  hash={policy.hash}",
        f"Factor:   {factor}",
        f"Protocol: {protocol.protocol_id}  primary_H={protocol.primary_horizon}  "
        f"report_H={list(protocol.horizons_report)}",
        "Methods:  univariate IC + drop ablation (zero factor)",
        f"Panel n:  {n_rows}   Folds: {len(fold_metrics)}",
        f"Verdict:  {verdict.value}",
        "",
        f"Primary @ H={protocol.primary_horizon} (mean OOS folds):",
        f"  univariate IC(factor, excess): {fmt(mean_u)}",
        f"  delta IC (full - drop):       {fmt(mean_delta)}  "
        "(positive => factor helps production)",
        f"  folds with delta>0:           {agree_s}",
        "",
        "Horizon table (pooled OOS):",
    ]
    full_h = horizon_metrics.get("full") or {}
    drop_h = horizon_metrics.get("drop") or {}
    uni_h = horizon_metrics.get("univariate") or {}
    for h in protocol.horizons_report:
        mark = "  <- primary" if h == protocol.primary_horizon else ""
        lines.append(
            f"  H={h:>2}: full={fmt(full_h.get(str(h)))}  drop={fmt(drop_h.get(str(h)))}  "
            f"univ={fmt(uni_h.get(str(h)))}{mark}"
        )
    lines.append("")
    lines.append("Folds:")
    for f in fold_metrics:
        lines.append(
            f"  fold {f['fold']}: n_test={f['n_test']}  "
            f"ic_full={fmt(f.get('ic_full'))}  ic_drop={fmt(f.get('ic_drop'))}  "
            f"delta={fmt(f.get('delta_ic'))}  univ={fmt(f.get('univariate_ic'))}"
        )
    lines.append("")
    lines.append("Costs: gross · Not investment advice · Never auto-promotes ai-saham config.")
    if notes:
        lines.append("")
        lines.append("Notes:")
        for n in notes[:12]:
            lines.append(f"  - {n}")
    return lines


def _format_factor_summary(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    factor: str,
    verdict: FactorVerdict,
    mean_delta: float | None,
    mean_u: float | None,
    horizon_metrics: dict,
    notes: list[str],
) -> str:
    def fmt(x: float | None) -> str:
        return f"{x:+.4f}" if x is not None else "n/a"

    lines = [
        f"# Factor validity: {factor}",
        "",
        f"- **Policy:** {policy.policy_id} (`{policy.hash}`)",
        f"- **Verdict:** {verdict.value}",
        f"- **Protocol:** {protocol.protocol_id} (primary H={protocol.primary_horizon})",
        f"- **Univariate IC:** {fmt(mean_u)}",
        f"- **ΔIC (full − drop):** {fmt(mean_delta)}",
        "",
        "## Horizons",
        "",
    ]
    full_h = horizon_metrics.get("full") or {}
    drop_h = horizon_metrics.get("drop") or {}
    uni_h = horizon_metrics.get("univariate") or {}
    for h in protocol.horizons_report:
        lines.append(
            f"- H={h}: full={fmt(full_h.get(str(h)))}, drop={fmt(drop_h.get(str(h)))}, "
            f"univ={fmt(uni_h.get(str(h)))}"
        )
    lines.extend(["", "## Notes", ""])
    for n in notes[:20]:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("Do **not** auto-edit ai-saham. Human review required.")
    lines.append("")
    return "\n".join(lines)
