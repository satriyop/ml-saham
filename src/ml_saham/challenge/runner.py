"""ADR-002 policy challenge runner."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ml_saham.challenge.artifacts import write_challenge_artifact
from ml_saham.challenge.metrics import bottom_decile_mean, ic_safe, time_purged_folds
from ml_saham.challenge.panel import PanelRow, build_panel
from ml_saham.challenge.panel_iev import build_iev_panel
from ml_saham.challenge.panel_pre_open_obs import build_pre_open_obs_panel
from ml_saham.challenge.policies.registry import list_policy_ids, load_policy
from ml_saham.challenge.protocols import ACCUM_PATH_V1, get_protocol
from ml_saham.challenge.scorers import (
    score_equal_sleeves,
    score_production,
    score_ridge_reweight,
)
from dataclasses import dataclass

from ml_saham.challenge.types import ChallengeResult, ChallengeStatus, PolicySnapshot, Protocol
from ml_saham.data.aisaham_read import has_ihsg, table_exists
from ml_saham.data.aisaham_read import connect as db_connect
from ml_saham.data.doctor_checks import run_doctor


@dataclass
class AccumPanelPrep:
    """Shared prep for policy tournament and factor validity (any panel_kind)."""

    policy: PolicySnapshot | None
    protocol: Protocol | None
    rows: list[PanelRow]
    notes: list[str]
    blocked: ChallengeStatus | None  # None if ready to score


def list_policies() -> list[dict[str, str]]:
    out = []
    for pid in list_policy_ids():
        pol = load_policy(pid)
        out.append(
            {
                "policy_id": pol.policy_id,
                "version": pol.version,
                "hash": pol.hash,
                "protocol": pol.protocol_id,
                "panel_kind": pol.panel_kind,
                "score_kind": pol.score_kind,
            }
        )
    return out


def _vet_for_accum(db_path: Path, protocol: Protocol) -> tuple[bool, list[str]]:
    notes: list[str] = []
    report = run_doctor(db_path, deep=True)
    if not report.db_exists:
        return False, ["DB file not found"]
    if not report.mvp_hard_ok:
        return False, ["MVP hard data checks failed — run ml-saham doctor"]
    with db_connect(db_path) as conn:
        if not has_ihsg(conn):
            return False, ["IHSG candles required for excess labels"]
    # accum observations soft→hard for this protocol
    obs_item = next(
        (i for i in report.integrity.items if i.name == "learning_observations"),
        None,
    )
    if obs_item is None or obs_item.status == "missing":
        return False, ["learning_observations missing/empty for accum challenge"]
    if obs_item.status == "partial":
        notes.append(f"thin observations: {obs_item.detail}")
    return True, notes


def _vet_for_pre_open_iev(db_path: Path, protocol: Protocol) -> tuple[bool, list[str]]:
    del protocol
    notes: list[str] = []
    report = run_doctor(db_path, deep=False)
    if not report.db_exists:
        return False, ["DB file not found"]
    if not report.mvp_hard_ok:
        return False, ["MVP hard data checks failed — run ml-saham doctor"]
    with db_connect(db_path) as conn:
        if not has_ihsg(conn):
            return False, ["IHSG candles required for open→close excess labels"]
        has_hist = table_exists(conn, "iev_snapshot_history")
        has_snap = table_exists(conn, "iev_snapshots")
        n_hist = 0
        n_snap = 0
        if has_hist:
            n_hist = int(
                conn.execute("SELECT COUNT(*) AS n FROM iev_snapshot_history").fetchone()["n"]
            )
        if has_snap:
            n_snap = int(conn.execute("SELECT COUNT(*) AS n FROM iev_snapshots").fetchone()["n"])
        if n_hist == 0 and n_snap == 0:
            return False, ["iev_snapshots / iev_snapshot_history empty or missing"]
        if n_hist == 0 and n_snap > 0:
            notes.append("iev_snapshot_history missing; using iev_snapshots")
        # thin calendar soft note
        table = "iev_snapshot_history" if n_hist > 0 else "iev_snapshots"
        n_dates = int(
            conn.execute(f"SELECT COUNT(DISTINCT date) AS n FROM {table}").fetchone()["n"]
        )
        if n_dates < 5:
            notes.append(f"thin IEV calendar: {n_dates} distinct dates")
    return True, notes


def _vet_for_pre_open_obs(db_path: Path, protocol: Protocol) -> tuple[bool, list[str]]:
    del protocol
    notes: list[str] = []
    report = run_doctor(db_path, deep=False)
    if not report.db_exists:
        return False, ["DB file not found"]
    if not report.mvp_hard_ok:
        return False, ["MVP hard data checks failed — run ml-saham doctor"]
    with db_connect(db_path) as conn:
        if not has_ihsg(conn):
            return False, ["IHSG candles required for open-path excess labels"]
        if not table_exists(conn, "learning_observations"):
            return False, ["learning_observations missing (need PRE_OPEN captures)"]
        n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM learning_observations "
                "WHERE purpose = 'PRE_OPEN_AUCTION_DIRECTION' "
                "OR purpose LIKE '%PRE_OPEN%'"
            ).fetchone()["n"]
        )
        if n == 0:
            return False, [
                "no PRE_OPEN_AUCTION_DIRECTION rows in learning_observations "
                "(product ready; wait for denser ai-saham captures)"
            ]
        if n < 80:
            notes.append(
                f"thin PRE_OPEN observations n={n} (tournament needs denser panel)"
            )
    return True, notes


def _select_rows(rows: Sequence[PanelRow], idx: Sequence[int]) -> list[PanelRow]:
    return [rows[i] for i in idx]


def prepare_accum_panel(
    db_path: Path | str,
    policy_id: str = "screener.accum.score_weights",
    protocol_id: str | None = None,
) -> AccumPanelPrep:
    """Load policy, vet DB, build labeled panel. blocked set if not runnable.

    Dispatches on policy.panel_kind. protocol_id defaults to policy.protocol_id.
    """
    path = Path(db_path)
    try:
        policy = load_policy(policy_id)
        pid = protocol_id or policy.protocol_id
        protocol = get_protocol(pid)
    except KeyError as exc:
        return AccumPanelPrep(
            policy=None,
            protocol=None,
            rows=[],
            notes=[str(exc)],
            blocked=ChallengeStatus.BLOCKED_POLICY,
        )

    if policy.panel_kind == "iev_rank":
        ok, vet_notes = _vet_for_pre_open_iev(path, protocol)
        if not ok:
            return AccumPanelPrep(
                policy=policy,
                protocol=protocol,
                rows=[],
                notes=vet_notes,
                blocked=ChallengeStatus.BLOCKED_DATA,
            )
        rows, panel_notes = build_iev_panel(
            path,
            policy,
            primary_horizon=protocol.primary_horizon,
        )
    elif policy.panel_kind == "pre_open_observations":
        ok, vet_notes = _vet_for_pre_open_obs(path, protocol)
        if not ok:
            return AccumPanelPrep(
                policy=policy,
                protocol=protocol,
                rows=[],
                notes=vet_notes,
                blocked=ChallengeStatus.BLOCKED_DATA,
            )
        rows, panel_notes = build_pre_open_obs_panel(
            path,
            policy,
            primary_horizon=protocol.primary_horizon,
        )
    elif policy.panel_kind == "accum_components":
        ok, vet_notes = _vet_for_accum(path, protocol)
        if not ok:
            return AccumPanelPrep(
                policy=policy,
                protocol=protocol,
                rows=[],
                notes=vet_notes,
                blocked=ChallengeStatus.BLOCKED_DATA,
            )
        rows, panel_notes = build_panel(
            path,
            policy,
            horizons=protocol.horizons_report,
            primary_horizon=protocol.primary_horizon,
        )
    else:
        return AccumPanelPrep(
            policy=policy,
            protocol=protocol,
            rows=[],
            notes=[f"unsupported panel_kind={policy.panel_kind!r}"],
            blocked=ChallengeStatus.BLOCKED_POLICY,
        )

    notes = list(vet_notes) + list(panel_notes)
    if len(rows) < protocol.min_n_total:
        notes.append(
            f"panel too small n={len(rows)} < min_n_total={protocol.min_n_total}"
        )
        return AccumPanelPrep(
            policy=policy,
            protocol=protocol,
            rows=rows,
            notes=notes,
            blocked=ChallengeStatus.BLOCKED_DATA,
        )
    return AccumPanelPrep(
        policy=policy,
        protocol=protocol,
        rows=rows,
        notes=notes,
        blocked=None,
    )


def prepare_for_policy(
    db_path: Path | str,
    policy_id: str,
    protocol_id: str | None = None,
) -> AccumPanelPrep:
    """Alias: prep dispatch for any registered policy."""
    return prepare_accum_panel(db_path, policy_id, protocol_id)


def _horizon_ics(
    rows: Sequence[PanelRow],
    scores: Sequence[float],
    horizons: tuple[int, ...],
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for h in horizons:
        pairs_s: list[float] = []
        pairs_r: list[float] = []
        for r, s in zip(rows, scores, strict=True):
            if h in r.excess:
                pairs_s.append(s)
                pairs_r.append(r.excess[h])
        out[str(h)] = ic_safe(pairs_s, pairs_r) if len(pairs_s) >= 5 else None
    return out


def _verdict(
    protocol: Protocol,
    fold_rows: list[dict],
    *,
    baseline_id: str,
    against_id: str,
) -> tuple[ChallengeStatus, float | None, float | None, list[str]]:
    notes: list[str] = []
    valid = [f for f in fold_rows if f.get("ic_baseline") is not None and f.get("ic_against") is not None]
    if not valid:
        return ChallengeStatus.INCONCLUSIVE, None, None, ["no valid folds with IC"]

    base_ics = [float(f["ic_baseline"]) for f in valid]
    ag_ics = [float(f["ic_against"]) for f in valid]
    mean_b = sum(base_ics) / len(base_ics)
    mean_a = sum(ag_ics) / len(ag_ics)

    fold_wins = sum(1 for f in valid if float(f["ic_against"]) > float(f["ic_baseline"]) + 1e-12)
    agree = fold_wins / len(valid)

    # tail: against should not be much worse on bottom-decile mean excess
    tail_ok = True
    for f in valid:
        tb = f.get("tail_baseline")
        ta = f.get("tail_against")
        if tb is not None and ta is not None and ta < tb - 0.005:
            tail_ok = False
            notes.append("tail proxy worse on at least one fold")
            break

    if mean_a > mean_b + protocol.win_margin and agree >= protocol.min_fold_agree and tail_ok:
        return ChallengeStatus.WIN, mean_b, mean_a, notes
    if mean_a > mean_b + protocol.win_margin and agree < protocol.min_fold_agree:
        notes.append(f"IC edge but fold agree {agree:.0%} < {protocol.min_fold_agree:.0%}")
        return ChallengeStatus.INCONCLUSIVE, mean_b, mean_a, notes
    if abs(mean_a - mean_b) <= protocol.win_margin:
        notes.append("primary IC within margin")
        return ChallengeStatus.INCONCLUSIVE, mean_b, mean_a, notes
    return ChallengeStatus.LOSE, mean_b, mean_a, notes


def run_policy_challenge(
    db_path: Path | str,
    policy_id: str = "screener.accum.score_weights",
    *,
    against: str = "ridge_reweight",
    baseline: str = "production",
    protocol_id: str | None = None,
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> ChallengeResult:
    path = Path(db_path)
    against = against.strip().lower().replace("-", "_")
    baseline = baseline.strip().lower().replace("-", "_")
    if baseline not in ("production",):
        baseline = "production"

    prep = prepare_for_policy(path, policy_id, protocol_id)
    if prep.blocked is not None or prep.policy is None or prep.protocol is None:
        st = prep.blocked or ChallengeStatus.BLOCKED_DATA
        return ChallengeResult(
            status=st,
            policy_id=policy_id if prep.policy is None else prep.policy.policy_id,
            protocol_id=(
                (protocol_id or "")
                if prep.protocol is None
                else prep.protocol.protocol_id
            ),
            baseline_id=baseline,
            against_id=against,
            policy_hash="" if prep.policy is None else prep.policy.hash,
            n_rows=len(prep.rows),
            primary_horizon=(
                ACCUM_PATH_V1.primary_horizon
                if prep.protocol is None
                else prep.protocol.primary_horizon
            ),
            lines=[f"{st.value}:"] + [f"  - {n}" for n in prep.notes],
            summary_md=f"# Challenge {st.value}\n\n"
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
        return ChallengeResult(
            status=ChallengeStatus.BLOCKED_DATA,
            policy_id=policy.policy_id,
            protocol_id=protocol.protocol_id,
            baseline_id=baseline,
            against_id=against,
            policy_hash=policy.hash,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon,
            lines=["BLOCKED_DATA: could not form time folds"],
            summary_md="# Challenge BLOCKED_DATA\n\nNo time folds.\n",
            notes=notes + ["no folds"],
        )

    fold_metrics: list[dict] = []
    last_coefs: dict[str, float] = {}
    oos_base_scores: list[float] = []
    oos_ag_scores: list[float] = []
    oos_rows: list[PanelRow] = []

    for fi, fold in enumerate(folds):
        train = _select_rows(rows, fold.train_idx)
        test = _select_rows(rows, fold.test_idx)
        base_s = score_production(test, policy)

        if against in ("equal_sleeves", "equal"):
            ag_s = score_equal_sleeves(test, policy)
            coefs = {c.key: 1.0 for c in policy.enabled_components()}
        elif against in ("ridge_reweight", "ridge"):
            ag_s, coefs = score_ridge_reweight(
                train, test, policy, primary_horizon=protocol.primary_horizon
            )
            last_coefs = coefs
        elif against == "production":
            ag_s = score_production(test, policy)
            coefs = policy.weight_map()
        else:
            return ChallengeResult(
                status=ChallengeStatus.BLOCKED_POLICY,
                policy_id=policy.policy_id,
                protocol_id=protocol.protocol_id,
                baseline_id=baseline,
                against_id=against,
                policy_hash=policy.hash,
                n_rows=len(rows),
                primary_horizon=protocol.primary_horizon,
                lines=[f"Unknown challenger {against!r}. Use equal_sleeves|ridge_reweight"],
                notes=[f"unknown against={against}"],
            )

        ph = protocol.primary_horizon
        y = [r.excess[ph] for r in test if ph in r.excess]
        # align scores if any row missing primary (should not happen after panel filter)
        if len(y) != len(test):
            base_s = [s for r, s in zip(test, base_s, strict=True) if ph in r.excess]
            ag_s = [s for r, s in zip(test, ag_s, strict=True) if ph in r.excess]
            test = [r for r in test if ph in r.excess]
            y = [r.excess[ph] for r in test]
        ic_b = ic_safe(base_s, y)
        ic_a = ic_safe(ag_s, y)
        fold_metrics.append(
            {
                "fold": fi,
                "n_train": len(train),
                "n_test": len(test),
                "ic_baseline": ic_b,
                "ic_against": ic_a,
                "tail_baseline": bottom_decile_mean(base_s, y),
                "tail_against": bottom_decile_mean(ag_s, y),
                "date_min": test[0].date if test else None,
                "date_max": test[-1].date if test else None,
            }
        )
        oos_base_scores.extend(base_s)
        oos_ag_scores.extend(ag_s)
        oos_rows.extend(test)

    status, mean_b, mean_a, vnotes = _verdict(
        protocol, fold_metrics, baseline_id=baseline, against_id=against
    )
    notes.extend(vnotes)

    hz_base = _horizon_ics(oos_rows, oos_base_scores, protocol.horizons_report)
    hz_ag = _horizon_ics(oos_rows, oos_ag_scores, protocol.horizons_report)
    horizon_metrics = {
        "baseline": hz_base,
        "against": hz_ag,
    }

    prod_w = policy.weight_map()
    weights = {
        "production": prod_w,
        "against": last_coefs if against.startswith("ridge") else (
            {k: 1.0 for k in prod_w} if "equal" in against else prod_w
        ),
        "against_id": against,
    }

    lines = _format_lines(
        policy=policy,
        protocol=protocol,
        status=status,
        against=against,
        n_rows=len(rows),
        mean_b=mean_b,
        mean_a=mean_a,
        horizon_metrics=horizon_metrics,
        fold_metrics=fold_metrics,
        notes=notes,
    )
    summary = _format_summary(
        policy=policy,
        protocol=protocol,
        status=status,
        against=against,
        mean_b=mean_b,
        mean_a=mean_a,
        horizon_metrics=horizon_metrics,
        notes=notes,
    )

    result = ChallengeResult(
        status=status,
        policy_id=policy.policy_id,
        protocol_id=protocol.protocol_id,
        baseline_id=baseline,
        against_id=against,
        policy_hash=policy.hash,
        n_rows=len(rows),
        primary_horizon=protocol.primary_horizon,
        primary_ic_baseline=mean_b,
        primary_ic_against=mean_a,
        horizon_metrics=horizon_metrics,
        fold_metrics=fold_metrics,
        weights=weights,
        lines=lines,
        summary_md=summary,
        notes=notes,
    )
    if write_artifact:
        write_challenge_artifact(result, db_path=path, artifacts_root=artifacts_dir)
        if result.artifact_dir:
            result.lines.append(f"Artifact: {result.artifact_dir}")
    return result


def _format_lines(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    status: ChallengeStatus,
    against: str,
    n_rows: int,
    mean_b: float | None,
    mean_a: float | None,
    horizon_metrics: dict,
    fold_metrics: list[dict],
    notes: list[str],
) -> list[str]:
    def fmt(x: float | None) -> str:
        return f"{x:+.4f}" if x is not None else "n/a"

    label_blurb = protocol.label
    if protocol.primary_horizon == 0:
        h_primary_txt = "same-session open→close (H=0 sentinel)"
    else:
        h_primary_txt = f"H={protocol.primary_horizon}"

    lines = [
        "=== POLICY CHALLENGE (ADR-002) ===",
        f"Policy:   {policy.policy_id}  hash={policy.hash}",
        f"Protocol: {protocol.protocol_id}  primary={h_primary_txt}  "
        f"report_H={list(protocol.horizons_report)}",
        f"Label:    {label_blurb}",
        f"Baseline: production   Against: {against}",
        f"Panel n:  {n_rows}   Folds: {len(fold_metrics)}",
        f"Status:   {status.value}",
        "",
        f"Primary rank IC @ {h_primary_txt} (mean OOS folds):",
        f"  production: {fmt(mean_b)}",
        f"  {against}:  {fmt(mean_a)}",
        "",
        "Horizon table (pooled OOS rank IC):",
    ]
    base_h = horizon_metrics.get("baseline") or {}
    ag_h = horizon_metrics.get("against") or {}
    for h in protocol.horizons_report:
        mark = "  <- primary" if h == protocol.primary_horizon else ""
        hlab = "open→close" if h == 0 else str(h)
        lines.append(
            f"  H={hlab:>10}:  production={fmt(base_h.get(str(h)))}  "
            f"{against}={fmt(ag_h.get(str(h)))}{mark}"
        )
    lines.append("")
    lines.append("Folds:")
    for f in fold_metrics:
        lines.append(
            f"  fold {f['fold']}: n_test={f['n_test']}  "
            f"ic_prod={fmt(f.get('ic_baseline'))}  ic_ag={fmt(f.get('ic_against'))}  "
            f"dates={f.get('date_min')}..{f.get('date_max')}"
        )
    lines.append("")
    lines.append("Costs: gross (not including fees) · Not investment advice")
    lines.append("Never auto-promotes ai-saham config.")
    if notes:
        lines.append("")
        lines.append("Notes:")
        for n in notes[:12]:
            lines.append(f"  - {n}")
    return lines


def _format_summary(
    *,
    policy: PolicySnapshot,
    protocol: Protocol,
    status: ChallengeStatus,
    against: str,
    mean_b: float | None,
    mean_a: float | None,
    horizon_metrics: dict,
    notes: list[str],
) -> str:
    def fmt(x: float | None) -> str:
        return f"{x:+.4f}" if x is not None else "n/a"

    htxt = (
        "same-session open→close"
        if protocol.primary_horizon == 0
        else f"H={protocol.primary_horizon}"
    )
    lines = [
        f"# Challenge: {policy.policy_id}",
        "",
        f"- **Status:** {status.value}",
        f"- **Protocol:** {protocol.protocol_id} (primary {htxt})",
        f"- **Label:** {protocol.label}",
        f"- **Baseline:** production (`{policy.hash}`)",
        f"- **Against:** {against}",
        f"- **Primary IC:** production={fmt(mean_b)} · {against}={fmt(mean_a)}",
        "",
        "## Horizons",
        "",
    ]
    base_h = horizon_metrics.get("baseline") or {}
    ag_h = horizon_metrics.get("against") or {}
    for h in protocol.horizons_report:
        hlab = "open→close" if h == 0 else str(h)
        lines.append(
            f"- H={hlab}: production={fmt(base_h.get(str(h)))}, "
            f"{against}={fmt(ag_h.get(str(h)))}"
        )
    lines.extend(["", "## Notes", ""])
    for n in notes[:20]:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("Do **not** auto-promote. Human review required.")
    lines.append("")
    return "\n".join(lines)
