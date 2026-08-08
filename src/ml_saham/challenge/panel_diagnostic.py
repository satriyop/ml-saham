"""Strict schema-15 diagnostic panel over verified ACCUM observations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml_saham.challenge.diagnostic_producer_bindings import (
    DiagnosticBindingError,
    OBSERVATION_SCHEMA_VERSION,
    VerifiedDiagnosticBinding,
    verify_diagnostic_observation_bindings,
)
from ml_saham.challenge.diagnostics.registry import DIAGNOSTIC_REGIME_MAP
from ml_saham.challenge.panel import build_forward_excess, extract_components
from ml_saham.challenge.policies.registry import load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import (
    PolicySnapshotError,
    compose_execution_policy,
    load_verified_snapshot_set,
)
from ml_saham.challenge.scorers import score_production
from ml_saham.challenge.types import ChallengeExecutionPolicy, DiagnosticSpec
from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.observation_cohort import (
    ACCUM_PURPOSES,
    ACCUM_PURPOSE_LIKE,
    fetch_accum_observation_raw,
    require_family_compatibility_id,
)


class DiagnosticPanelBindingError(ValueError):
    """A production-facing diagnostic panel is not exactly authority-bound."""


@dataclass(frozen=True)
class DiagnosticPanelIdentity:
    observation_compatibility_id: str
    diagnostic_compatibility_id: str
    producer_snapshot_ids: tuple[str, ...]
    producer_payload_digests: tuple[str, ...]
    producer_source_revisions: tuple[str, ...]
    action_policy_snapshot_ids: tuple[str, ...]
    action_policy_payload_digests: tuple[str, ...]
    action_policy_source_revisions: tuple[str, ...]
    population_identity_id: str
    session_start: str
    session_end: str
    cutoff_start: str
    cutoff_end: str
    observation_schema_version: int = OBSERVATION_SCHEMA_VERSION


@dataclass
class DiagnosticPanelRow:
    ticker: str
    date: str
    features: dict[str, float]
    production_score: float
    excess: dict[int, float]


def _numeric(value: Any) -> float | None:
    if type(value) in (int, float):
        return float(value)
    return None


def _window_7(payload: dict[str, Any]) -> dict[str, Any]:
    windows = payload.get("features_by_window")
    if not isinstance(windows, dict) or set(windows) != {"7", "30", "90"}:
        raise DiagnosticPanelBindingError(
            "schema-15 features_by_window must be 7/30/90"
        )
    window = windows.get("7")
    if not isinstance(window, dict):
        raise DiagnosticPanelBindingError(
            "schema-15 canonical diagnostic window 7 missing"
        )
    return window


def _window_views(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    window = _window_7(payload)
    signal = window.get("signal")
    fingerprint = window.get("sub_signal_fingerprint")
    candidate = window.get("candidate")
    if not isinstance(signal, dict) or not isinstance(fingerprint, dict):
        raise DiagnosticPanelBindingError("window 7 signal/fingerprint missing")
    if not isinstance(candidate, dict):
        raise DiagnosticPanelBindingError("window 7 candidate missing")
    return signal, fingerprint, candidate


def _group_score(signal: dict[str, Any], group_name: str) -> float | None:
    alpha = signal.get("alpha_trigger_score")
    if not isinstance(alpha, dict):
        return None
    groups = alpha.get("group_contributions")
    if not isinstance(groups, list):
        return None
    for row in groups:
        if not isinstance(row, dict) or row.get("group") != group_name:
            continue
        return _numeric(row.get("score"))
    return None


def extract_frozen_market_context_features(payload: dict[str, Any]) -> dict[str, float]:
    shared = payload.get("shared")
    context = shared.get("market_context") if isinstance(shared, dict) else None
    if not isinstance(context, dict):
        return {}
    found: dict[str, float] = {}
    regime = context.get("regime")
    if isinstance(regime, str):
        mapped = DIAGNOSTIC_REGIME_MAP.get(regime.strip().upper())
        if mapped is not None:
            found["regime_score"] = mapped
    factors = context.get("factors")
    if isinstance(factors, list):
        for row in factors:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                continue
            numeric = _numeric(row.get("value"))
            if numeric is not None:
                found[str(row["name"]).lower()] = numeric
    return found


def extract_diagnostic_features(
    payload: dict[str, Any], spec: DiagnosticSpec
) -> dict[str, float] | None:
    """Extract only schema-15 canonical lineage; no aliases or live reloads."""

    signal, fingerprint, _candidate = _window_views(payload)
    enabled = tuple(feature.key for feature in spec.enabled_features())
    found: dict[str, float] = {}
    if spec.diagnostic_id == "mce.screen_display":
        context = extract_frozen_market_context_features(payload)
        found = {key: context[key] for key in enabled if key in context}
    elif spec.diagnostic_id == "sector.peer_context":
        score = _group_score(signal, "sector_context")
        breadth = _numeric(fingerprint.get("sc_sector_breadth"))
        if score is not None and "sector_context_score" in enabled:
            found["sector_context_score"] = score
        if breadth is not None and "peer_breadth" in enabled:
            found["peer_breadth"] = breadth
    elif spec.diagnostic_id == "institutional.accumulation_bag":
        score = _group_score(signal, "institutional_flow")
        if score is not None and "institutional_flow_score" in enabled:
            found["institutional_flow_score"] = score
        for key in ("ia_foreign_participation", "ia_domestic_buy_vwap_distance"):
            value = _numeric(fingerprint.get(key))
            if value is not None and key in enabled:
                found[key] = value
    elif spec.diagnostic_id == "company_quality.bag":
        score = _group_score(signal, "company_quality_context")
        if score is not None and "company_quality_score" in enabled:
            found["company_quality_score"] = score
        for key in ("cq_valuation_score", "tp_liquidity_score"):
            value = _numeric(fingerprint.get(key))
            if value is not None and key in enabled:
                found[key] = value
    else:
        raise DiagnosticPanelBindingError(
            f"unsupported diagnostic_id={spec.diagnostic_id!r}"
        )
    if not found:
        return None
    return {key: found.get(key, float("nan")) for key in enabled}


def _production_score(
    payload: dict[str, Any], policy: ChallengeExecutionPolicy
) -> float:
    window = _window_7(payload)
    components = extract_components(
        {"canonical_window": 7, "features_by_window": {"7": window}}, policy
    )
    if not components:
        raise DiagnosticPanelBindingError(
            "verified production control components missing"
        )
    from ml_saham.challenge.panel import PanelRow

    row = PanelRow(ticker="X", date="1970-01-01", components=components, excess={})
    return float(score_production([row], policy)[0])


def _parse_payloads(rows: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        raw = row["decision_payload_json"] if isinstance(row, sqlite3.Row) else row[2]
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiagnosticPanelBindingError(
                "malformed decision_payload_json"
            ) from exc
        if not isinstance(payload, dict):
            raise DiagnosticPanelBindingError("decision payload must be an object")
        payloads.append(payload)
    return payloads


def build_diagnostic_panel(
    db_path: Path | str,
    spec: DiagnosticSpec,
    horizons: tuple[int, ...],
    primary_horizon: int,
    *,
    compatibility_id: str | None,
    diagnostic_compatibility_id: str | None,
) -> tuple[list[DiagnosticPanelRow], list[str], DiagnosticPanelIdentity]:
    """Build a fully verified, non-promotable diagnostic panel."""

    path = Path(db_path)
    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            raise DiagnosticPanelBindingError("learning_observations missing")
        selected, notes = require_family_compatibility_id(
            conn,
            purposes=ACCUM_PURPOSES,
            purpose_like=ACCUM_PURPOSE_LIKE,
            preferred=compatibility_id,
            family="ACCUM",
        )
        if selected is None:
            raise DiagnosticPanelBindingError("; ".join(notes))
        rows_raw, cohort_notes, _ = fetch_accum_observation_raw(
            conn, compatibility_id=selected
        )
        notes.extend(cohort_notes)
        payloads = _parse_payloads(rows_raw)
        population_ids: set[str] = set()
        cutoffs: list[str] = []
        sessions: list[str] = []
        for payload in payloads:
            population = payload.get("population_binding")
            population_id = (
                population.get("membership_digest")
                if isinstance(population, dict)
                else None
            )
            shared = payload.get("shared")
            provenance = shared.get("provenance") if isinstance(shared, dict) else None
            cutoff = (
                provenance.get("decision_at") if isinstance(provenance, dict) else None
            )
            session = payload.get("session_date")
            if not isinstance(population_id, str) or not population_id:
                raise DiagnosticPanelBindingError(
                    "schema-15 population identity missing"
                )
            if (
                not isinstance(cutoff, str)
                or not cutoff
                or not isinstance(session, str)
            ):
                raise DiagnosticPanelBindingError(
                    "schema-15 session/cutoff provenance missing"
                )
            population_ids.add(population_id)
            cutoffs.append(cutoff)
            sessions.append(session)
        if len(population_ids) != 1:
            raise DiagnosticPanelBindingError(
                "mixed population identity in diagnostic cohort"
            )
        try:
            snapshots = load_verified_snapshot_set(conn, selected)
            binding: VerifiedDiagnosticBinding = verify_diagnostic_observation_bindings(
                conn,
                diagnostic_id=spec.diagnostic_id,
                diagnostic_compatibility_id=diagnostic_compatibility_id,
                decision_payloads=payloads,
            )
            control = compose_execution_policy(
                snapshots["screener.accum.score_weights"],
                load_policy_adapter("screener.accum.score_weights"),
            )
        except (DiagnosticBindingError, PolicySnapshotError, KeyError) as exc:
            raise DiagnosticPanelBindingError(str(exc)) from exc

        candidates: list[tuple[str, str, dict[str, float], float]] = []
        for payload in payloads:
            ticker = payload.get("ticker")
            date = payload.get("session_date")
            if not isinstance(ticker, str) or not isinstance(date, str):
                raise DiagnosticPanelBindingError("ticker/session_date missing")
            features = extract_diagnostic_features(payload, spec)
            if features is None:
                continue
            candidates.append(
                (ticker.upper(), date, features, _production_score(payload, control))
            )
        if not candidates:
            raise DiagnosticPanelBindingError(
                "no diagnostic-extractable observation rows"
            )

        excess_map = build_forward_excess(
            conn, sorted({ticker for ticker, _, _, _ in candidates}), horizons
        )
        if not excess_map:
            raise DiagnosticPanelBindingError("IHSG-aligned forward excess unavailable")
        output: list[DiagnosticPanelRow] = []
        dropped = 0
        for ticker, date, features, production_score in candidates:
            excess = excess_map.get((ticker, date))
            if not excess or primary_horizon not in excess:
                dropped += 1
                continue
            output.append(
                DiagnosticPanelRow(ticker, date, features, production_score, excess)
            )
        if dropped:
            notes.append(f"dropped {dropped} rows missing primary H={primary_horizon}")
        notes.append(
            f"diagnostic_panel n={len(output)} diagnostic_id={spec.diagnostic_id}"
        )
        return (
            output,
            notes,
            DiagnosticPanelIdentity(
                observation_compatibility_id=selected,
                diagnostic_compatibility_id=binding.compatibility_id,
                producer_snapshot_ids=binding.producer_snapshot_ids,
                producer_payload_digests=binding.producer_payload_digests,
                producer_source_revisions=binding.producer_source_revisions,
                action_policy_snapshot_ids=tuple(
                    s.snapshot_id for s in snapshots.values()
                ),
                action_policy_payload_digests=tuple(
                    s.payload_digest for s in snapshots.values()
                ),
                action_policy_source_revisions=tuple(
                    s.source_revision for s in snapshots.values()
                ),
                population_identity_id=next(iter(population_ids)),
                session_start=min(sessions),
                session_end=max(sessions),
                cutoff_start=min(cutoffs),
                cutoff_end=max(cutoffs),
            ),
        )
