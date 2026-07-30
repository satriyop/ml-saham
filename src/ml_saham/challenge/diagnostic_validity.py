"""Diagnostic validity track: calibration of explain-only bags.

Verdicts: KEEP_DISPLAY / DEMOTE_DISPLAY / DROP_DISPLAY / PROMOTE_CANDIDATE.
Never Action authority. Never WIN/LOSE vs production weights.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from ml_saham.challenge.artifacts import (
    write_batch_diagnostic_artifact,
    write_diagnostic_artifact,
)
from ml_saham.challenge.diagnostics.registry import (
    list_diagnostics,
    load_diagnostic,
    resolve_feature_key,
)
from ml_saham.challenge.metrics import Fold, ic_safe, time_purged_folds
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.panel_diagnostic import DiagnosticPanelRow, build_diagnostic_panel
from ml_saham.challenge.protocols import ACCUM_PATH_V1, get_protocol
from ml_saham.challenge.types import (
    BatchDiagnosticResult,
    DiagnosticChallengeResult,
    DiagnosticSpec,
    DiagnosticVerdict,
    Protocol,
)


def list_diagnostic_catalog() -> list[dict[str, object]]:
    return list_diagnostics()


def list_enabled_diagnostic_features(
    diagnostic_id: str,
) -> list[dict[str, object]]:
    spec = load_diagnostic(diagnostic_id)
    return [
        {"key": f.key, "aliases": list(f.aliases), "note": f.note}
        for f in spec.enabled_features()
    ]


def _as_panel_rows(rows: Sequence[DiagnosticPanelRow]) -> list[PanelRow]:
    """Adapter so time_purged_folds can sort by date/ticker."""
    return [
        PanelRow(
            ticker=r.ticker,
            date=r.date,
            components=dict(r.features),
            excess=dict(r.excess),
        )
        for r in rows
    ]


def _feature_values(
    rows: Sequence[DiagnosticPanelRow],
    feature: str,
) -> list[float]:
    return [float(r.features.get(feature, float("nan"))) for r in rows]


def _coverage(vals: Sequence[float]) -> float:
    if not vals:
        return 0.0
    ok = sum(1 for v in vals if v == v)  # not NaN
    return ok / len(vals)


def _finite_pairs(
    xs: Sequence[float],
    ys: Sequence[float],
) -> tuple[list[float], list[float]]:
    ox: list[float] = []
    oy: list[float] = []
    for x, y in zip(xs, ys, strict=True):
        if x == x and y == y:
            ox.append(float(x))
            oy.append(float(y))
    return ox, oy


def _residualize(y: Sequence[float], control: Sequence[float]) -> list[float]:
    """OLS residual y - a - b*control; if control degenerate, return y centered."""
    yy = np.asarray(y, dtype=float)
    cc = np.asarray(control, dtype=float)
    if len(yy) < 5 or float(np.std(cc)) < 1e-12:
        return list(yy - float(np.mean(yy)))
    # simple least squares
    x = np.column_stack([np.ones(len(cc)), cc])
    try:
        coef, _, _, _ = np.linalg.lstsq(x, yy, rcond=None)
        pred = x @ coef
        return list(yy - pred)
    except np.linalg.LinAlgError:
        return list(yy - float(np.mean(yy)))


def _corr_abs(a: Sequence[float], b: Sequence[float]) -> float | None:
    aa, bb = _finite_pairs(a, b)
    if len(aa) < 5:
        return None
    if float(np.std(aa)) < 1e-12 or float(np.std(bb)) < 1e-12:
        return None
    return float(abs(np.corrcoef(aa, bb)[0, 1]))


def _univariate_and_residual_ics(
    rows: Sequence[DiagnosticPanelRow],
    feature: str,
    horizons: tuple[int, ...],
) -> tuple[dict[str, float | None], dict[str, float | None], float | None]:
    uni: dict[str, float | None] = {}
    res: dict[str, float | None] = {}
    xs_all = _feature_values(rows, feature)
    redun = _corr_abs(xs_all, [r.production_score for r in rows])
    for h in horizons:
        xs: list[float] = []
        ys: list[float] = []
        cs: list[float] = []
        for r in rows:
            v = r.features.get(feature, float("nan"))
            if v != v or h not in r.excess:
                continue
            xs.append(float(v))
            ys.append(float(r.excess[h]))
            cs.append(float(r.production_score))
        if len(xs) < 5:
            uni[str(h)] = None
            res[str(h)] = None
            continue
        uni[str(h)] = ic_safe(xs, ys)
        resid = _residualize(ys, cs)
        res[str(h)] = ic_safe(xs, resid)
    return uni, res, redun


def _diagnostic_verdict(
    protocol: Protocol,
    *,
    coverage: float,
    mean_u: float | None,
    mean_r: float | None,
    redundancy: float | None,
    fold_agree_res_pos: float | None,
) -> tuple[DiagnosticVerdict, list[str]]:
    notes: list[str] = []
    eps = protocol.win_margin
    abs_u = abs(mean_u) if mean_u is not None else 0.0
    abs_r = abs(mean_r) if mean_r is not None else 0.0
    red = redundancy if redundancy is not None else 0.0
    agree = fold_agree_res_pos if fold_agree_res_pos is not None else 0.0

    if coverage < 0.15:
        notes.append(f"coverage={coverage:.0%} too low")
        return DiagnosticVerdict.DROP_DISPLAY, notes

    if coverage < 0.35:
        notes.append(f"coverage={coverage:.0%} thin")

    # Promote: residual signal material + stable + not pure redundancy
    if (
        mean_r is not None
        and abs_r >= eps
        and agree >= protocol.min_fold_agree
        and red < 0.85
    ):
        notes.append("residual IC material after production score control")
        if red >= 0.6:
            notes.append(f"moderate redundancy |corr|={red:.2f} with production score")
        return DiagnosticVerdict.PROMOTE_CANDIDATE, notes

    # Pure redundancy with strong univariate only
    if red >= 0.85 and abs_u >= eps:
        notes.append("highly redundant with production score — weak new display value")
        return DiagnosticVerdict.DEMOTE_DISPLAY, notes

    # Keep display: some univariate or residual association, ok coverage
    if coverage >= 0.35 and (abs_u >= eps * 0.5 or abs_r >= eps * 0.5):
        notes.append("calibrated enough for explain-only display")
        return DiagnosticVerdict.KEEP_DISPLAY, notes

    # Drop: no signal
    if abs_u < eps * 0.5 and abs_r < eps * 0.5:
        notes.append("weak univariate and residual IC")
        if coverage < 0.5:
            return DiagnosticVerdict.DROP_DISPLAY, notes
        return DiagnosticVerdict.DEMOTE_DISPLAY, notes

    if agree < protocol.min_fold_agree and mean_r is not None:
        notes.append(f"fold residual agree={agree:.0%}")
        return DiagnosticVerdict.INCONCLUSIVE, notes

    return DiagnosticVerdict.INCONCLUSIVE, notes + ["conflicting calibration signals"]


def _run_one_feature(
    rows: Sequence[DiagnosticPanelRow],
    folds: list[Fold],
    spec: DiagnosticSpec,
    protocol: Protocol,
    feature: str,
) -> DiagnosticChallengeResult:
    xs_all = _feature_values(rows, feature)
    cov = _coverage(xs_all)
    uni_h, res_h, redun = _univariate_and_residual_ics(
        rows, feature, protocol.horizons_report
    )
    ph = str(protocol.primary_horizon)
    mean_u = uni_h.get(ph)
    mean_r = res_h.get(ph)

    fold_metrics: list[dict] = []
    for i, fold in enumerate(folds):
        test = [rows[j] for j in fold.test_idx]
        u_map, r_map, _ = _univariate_and_residual_ics(
            test, feature, (protocol.primary_horizon,)
        )
        u = u_map.get(ph)
        r = r_map.get(ph)
        fold_metrics.append(
            {
                "fold": i,
                "n_test": len(test),
                "univariate_ic": u,
                "residual_ic": r,
            }
        )

    valid_res = [f for f in fold_metrics if f.get("residual_ic") is not None]
    agree = None
    if valid_res:
        agree = sum(
            1 for f in valid_res if abs(float(f["residual_ic"])) >= protocol.win_margin * 0.5
            or float(f["residual_ic"]) > 0
        ) / len(valid_res)
        # prefer sign agreement on positive residual IC (information direction free for display)
        agree = sum(1 for f in valid_res if float(f["residual_ic"]) > 0) / len(valid_res)

    verdict, vnotes = _diagnostic_verdict(
        protocol,
        coverage=cov,
        mean_u=mean_u,
        mean_r=mean_r,
        redundancy=redun,
        fold_agree_res_pos=agree,
    )

    notes = list(vnotes)
    notes.append(spec.banner)

    lines = [
        "DIAGNOSTIC VALIDITY (not Action authority)",
        f"  diagnostic_id={spec.diagnostic_id}  feature={feature}",
        f"  protocol={protocol.protocol_id}  primary_H={protocol.primary_horizon}",
        f"  n_rows={len(rows)}  coverage={cov:.0%}",
        f"  univariate_IC@H={_fmt(mean_u)}  residual_IC@H={_fmt(mean_r)}",
        f"  redundancy_|corr|_vs_production={_fmt(redun)}",
        f"  verdict={verdict.value}",
        "",
        "ADR-057: explain-only. PROMOTE_CANDIDATE → design a tune PolicySpec; never auto-wire.",
    ]
    for n in notes[:6]:
        lines.append(f"  note: {n}")

    md = [
        f"# Diagnostic validity — `{spec.diagnostic_id}` / `{feature}`",
        "",
        f"**Verdict:** `{verdict.value}`",
        "",
        f"> {spec.banner}",
        "",
        f"- Protocol: `{protocol.protocol_id}` primary H={protocol.primary_horizon}",
        f"- n_rows: {len(rows)}  coverage: {cov:.0%}",
        f"- Univariate IC: {_fmt(mean_u)}",
        f"- Residual IC (after production score): {_fmt(mean_r)}",
        f"- Redundancy |corr| vs production score: {_fmt(redun)}",
        "",
        "## Notes",
        "",
    ]
    for n in notes:
        md.append(f"- {n}")
    md.append("")
    if verdict == DiagnosticVerdict.PROMOTE_CANDIDATE:
        md.extend(
            [
                "## Next step (human)",
                "",
                "1. Design a production PolicySpec / DecisionPolicy wiring proposal.",
                "2. Run `ml-saham challenge run` / `challenge factor` (tune track).",
                "3. Promote-packet + human change in ai-saham — never auto.",
                "",
            ]
        )

    return DiagnosticChallengeResult(
        verdict=verdict,
        diagnostic_id=spec.diagnostic_id,
        protocol_id=protocol.protocol_id,
        diagnostic_hash=spec.hash,
        feature=feature,
        n_rows=len(rows),
        primary_horizon=protocol.primary_horizon,
        coverage=cov,
        mean_univariate_ic=mean_u,
        mean_residual_ic=mean_r,
        mean_redundancy=redun,
        fold_agree_residual_positive=agree,
        horizon_metrics={"univariate": uni_h, "residual": res_h},
        fold_metrics=fold_metrics,
        lines=lines,
        summary_md="\n".join(md) + "\n",
        notes=notes,
    )


def _fmt(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:.4f}"


def _prep(
    db_path: Path | str,
    diagnostic_id: str,
    protocol_id: str | None,
) -> tuple[
    DiagnosticSpec | None,
    Protocol | None,
    list[DiagnosticPanelRow],
    list[str],
    DiagnosticVerdict | None,
]:
    try:
        spec = load_diagnostic(diagnostic_id)
        proto_id = protocol_id or spec.protocol_id
        protocol = get_protocol(proto_id)
    except KeyError as exc:
        return None, None, [], [str(exc)], DiagnosticVerdict.BLOCKED_SPEC

    rows, notes = build_diagnostic_panel(
        db_path,
        spec,
        horizons=protocol.horizons_report,
        primary_horizon=protocol.primary_horizon,
    )
    if len(rows) < protocol.min_n_total:
        notes = list(notes) + [
            f"panel too small n={len(rows)} < min_n_total={protocol.min_n_total}"
        ]
        return spec, protocol, rows, notes, DiagnosticVerdict.BLOCKED_DATA
    return spec, protocol, rows, notes, None


def run_diagnostic_challenge(
    db_path: Path | str,
    diagnostic_id: str,
    *,
    feature: str,
    protocol_id: str | None = None,
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> DiagnosticChallengeResult:
    path = Path(db_path)
    feature_raw = feature.strip()

    spec, protocol, rows, notes, blocked = _prep(path, diagnostic_id, protocol_id)
    if blocked is not None or spec is None or protocol is None:
        msg = "; ".join(notes) if notes else blocked.value if blocked else "blocked"
        return DiagnosticChallengeResult(
            verdict=blocked or DiagnosticVerdict.BLOCKED_SPEC,
            diagnostic_id=diagnostic_id,
            protocol_id=protocol_id or (spec.protocol_id if spec else ""),
            diagnostic_hash=spec.hash if spec else "",
            feature=feature_raw,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon if protocol else ACCUM_PATH_V1.primary_horizon,
            lines=[f"{(blocked or DiagnosticVerdict.BLOCKED_SPEC).value}:", f"  - {msg}"],
            summary_md=f"# Diagnostic challenge blocked\n\n{msg}\n",
            notes=notes,
        )

    canon = resolve_feature_key(spec, feature_raw)
    if canon is None:
        enabled = ", ".join(f.key for f in spec.enabled_features())
        msg = f"unknown or disabled feature {feature_raw!r}. Enabled: {enabled}"
        return DiagnosticChallengeResult(
            verdict=DiagnosticVerdict.BLOCKED_SPEC,
            diagnostic_id=spec.diagnostic_id,
            protocol_id=protocol.protocol_id,
            diagnostic_hash=spec.hash,
            feature=feature_raw,
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon,
            lines=["BLOCKED_SPEC:", f"  - {msg}"],
            summary_md=f"# Diagnostic challenge BLOCKED_SPEC\n\n{msg}\n",
            notes=[msg],
        )

    fold_rows = _as_panel_rows(rows)
    folds = time_purged_folds(fold_rows, protocol)
    if not folds:
        # single full-sample evaluation
        folds = [
            Fold(train_idx=list(range(len(rows))), test_idx=list(range(len(rows))))
        ]
        notes = list(notes) + ["fold fallback: full sample (thin date span)"]

    result = _run_one_feature(rows, folds, spec, protocol, canon)
    result.notes = list(notes) + list(result.notes)

    if write_artifact:
        write_diagnostic_artifact(
            result, db_path=path, artifacts_root=artifacts_dir
        )
    return result


def run_diagnostic_challenge_batch(
    db_path: Path | str,
    diagnostic_id: str,
    *,
    protocol_id: str | None = None,
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> BatchDiagnosticResult:
    path = Path(db_path)
    spec, protocol, rows, notes, blocked = _prep(path, diagnostic_id, protocol_id)
    if blocked is not None or spec is None or protocol is None:
        msg = "; ".join(notes) if notes else "blocked"
        return BatchDiagnosticResult(
            diagnostic_id=diagnostic_id,
            protocol_id=protocol_id or "",
            diagnostic_hash=spec.hash if spec else "",
            n_rows=len(rows),
            primary_horizon=protocol.primary_horizon if protocol else ACCUM_PATH_V1.primary_horizon,
            blocked=blocked or DiagnosticVerdict.BLOCKED_SPEC,
            lines=[f"{(blocked or DiagnosticVerdict.BLOCKED_SPEC).value}:", f"  - {msg}"],
            summary_md=f"# Diagnostic batch blocked\n\n{msg}\n",
            notes=notes,
        )

    fold_rows = _as_panel_rows(rows)
    folds = time_purged_folds(fold_rows, protocol)
    if not folds:
        folds = [
            Fold(train_idx=list(range(len(rows))), test_idx=list(range(len(rows))))
        ]
        notes = list(notes) + ["fold fallback: full sample (thin date span)"]

    results: list[DiagnosticChallengeResult] = []
    for feat in spec.enabled_features():
        results.append(_run_one_feature(rows, folds, spec, protocol, feat.key))

    lines = [
        "DIAGNOSTIC VALIDITY BATCH (not Action authority)",
        f"  diagnostic_id={spec.diagnostic_id}  hash={spec.hash}",
        f"  protocol={protocol.protocol_id}  primary_H={protocol.primary_horizon}  n_rows={len(rows)}",
        f"  banner: {spec.banner}",
        "",
        f"{'feature':<22} {'verdict':<18} {'cov':>6} {'uniIC':>8} {'resIC':>8} {'redun':>6}",
        "-" * 72,
    ]
    for r in results:
        lines.append(
            f"{r.feature:<22} {r.verdict.value:<18} "
            f"{(r.coverage or 0):6.0%} {_fmt(r.mean_univariate_ic):>8} "
            f"{_fmt(r.mean_residual_ic):>8} {_fmt(r.mean_redundancy):>6}"
        )
    lines.append("")
    lines.append(
        "PROMOTE_CANDIDATE → design tune PolicySpec; never auto-wire into Action."
    )

    md = [
        f"# Diagnostic validity batch — `{spec.diagnostic_id}`",
        "",
        f"> {spec.banner}",
        "",
        f"- Protocol: `{protocol.protocol_id}` primary H={protocol.primary_horizon}",
        f"- n_rows: {len(rows)}",
        "",
        "| Feature | Verdict | Coverage | Uni IC | Residual IC | Redundancy |",
        "|---------|---------|----------|--------|-------------|------------|",
    ]
    for r in results:
        md.append(
            f"| {r.feature} | {r.verdict.value} | {(r.coverage or 0):.0%} | "
            f"{_fmt(r.mean_univariate_ic)} | {_fmt(r.mean_residual_ic)} | "
            f"{_fmt(r.mean_redundancy)} |"
        )
    md.extend(["", "## Notes", ""])
    for n in notes[:8]:
        md.append(f"- {n}")
    md.append("")

    batch = BatchDiagnosticResult(
        diagnostic_id=spec.diagnostic_id,
        protocol_id=protocol.protocol_id,
        diagnostic_hash=spec.hash,
        n_rows=len(rows),
        primary_horizon=protocol.primary_horizon,
        results=results,
        lines=lines,
        summary_md="\n".join(md) + "\n",
        notes=notes,
    )
    if write_artifact:
        write_batch_diagnostic_artifact(
            batch, db_path=path, artifacts_root=artifacts_dir
        )
    return batch


def run_diagnostic_health(
    db_path: Path | str,
    *,
    scenario: str | None = "accum",
    write_artifact: bool = True,
    artifacts_dir: Path | None = None,
) -> BatchDiagnosticResult:
    """Roll up all diagnostics for a scenario into one multi-bag batch report."""
    path = Path(db_path)
    sc = (scenario or "accum").strip().lower()
    ids = [
        d["diagnostic_id"]
        for d in list_diagnostics()
        if str(d.get("scenario") or "accum").lower() == sc
    ]
    if not ids:
        return BatchDiagnosticResult(
            diagnostic_id=f"_health.{sc}",
            protocol_id="",
            diagnostic_hash="",
            n_rows=0,
            primary_horizon=ACCUM_PATH_V1.primary_horizon,
            blocked=DiagnosticVerdict.BLOCKED_SPEC,
            lines=[f"BLOCKED_SPEC: no diagnostics registered for scenario={sc!r}"],
            summary_md=f"# Diagnostic health blocked\n\nNo bags for scenario={sc}\n",
            notes=[f"no diagnostics for scenario={sc}"],
        )

    all_results: list[DiagnosticChallengeResult] = []
    notes: list[str] = [f"diagnostic health scenario={sc}"]
    n_rows = 0
    protocol_id = ""
    for did in ids:
        batch = run_diagnostic_challenge_batch(
            path,
            str(did),
            write_artifact=False,
            artifacts_dir=artifacts_dir,
        )
        if batch.blocked is not None:
            notes.append(f"{did}: {batch.blocked.value}")
            # still record blocked as synthetic rows
            all_results.append(
                DiagnosticChallengeResult(
                    verdict=batch.blocked,
                    diagnostic_id=str(did),
                    protocol_id=batch.protocol_id,
                    diagnostic_hash=batch.diagnostic_hash,
                    feature="_bag",
                    n_rows=batch.n_rows,
                    primary_horizon=batch.primary_horizon,
                    notes=batch.notes[:3],
                )
            )
            continue
        protocol_id = batch.protocol_id
        n_rows = max(n_rows, batch.n_rows)
        for r in batch.results:
            # namespace feature with diagnostic id for health table
            all_results.append(
                DiagnosticChallengeResult(
                    verdict=r.verdict,
                    diagnostic_id=r.diagnostic_id,
                    protocol_id=r.protocol_id,
                    diagnostic_hash=r.diagnostic_hash,
                    feature=f"{r.diagnostic_id}:{r.feature}",
                    n_rows=r.n_rows,
                    primary_horizon=r.primary_horizon,
                    coverage=r.coverage,
                    mean_univariate_ic=r.mean_univariate_ic,
                    mean_residual_ic=r.mean_residual_ic,
                    mean_redundancy=r.mean_redundancy,
                    fold_agree_residual_positive=r.fold_agree_residual_positive,
                    notes=r.notes[:2],
                )
            )

    lines = [
        "DIAGNOSTIC HEALTH (not Action authority)",
        f"  scenario={sc}  n_bags={len(ids)}  max_n_rows={n_rows}",
        "",
        f"{'bag:feature':<40} {'verdict':<18} {'cov':>6} {'resIC':>8}",
        "-" * 76,
    ]
    for r in all_results:
        lines.append(
            f"{r.feature:<40} {r.verdict.value:<18} "
            f"{(r.coverage or 0):6.0%} {_fmt(r.mean_residual_ic):>8}"
        )
    lines.extend(
        [
            "",
            "ADR-057: display / promote-candidate only.",
            "PROMOTE_CANDIDATE → design tune PolicySpec; never auto-wire Action.",
        ]
    )

    md = [
        f"# Diagnostic health — scenario `{sc}`",
        "",
        "> ADR-057: not Action authority",
        "",
        "| Bag:feature | Verdict | Coverage | Residual IC |",
        "|-------------|---------|----------|-------------|",
    ]
    for r in all_results:
        md.append(
            f"| {r.feature} | {r.verdict.value} | {(r.coverage or 0):.0%} | "
            f"{_fmt(r.mean_residual_ic)} |"
        )
    md.append("")

    health = BatchDiagnosticResult(
        diagnostic_id=f"_health.{sc}",
        protocol_id=protocol_id,
        diagnostic_hash="health",
        n_rows=n_rows,
        primary_horizon=ACCUM_PATH_V1.primary_horizon,
        results=all_results,
        lines=lines,
        summary_md="\n".join(md) + "\n",
        notes=notes,
    )
    if write_artifact:
        write_batch_diagnostic_artifact(
            health, db_path=path, artifacts_root=artifacts_dir
        )
    return health
