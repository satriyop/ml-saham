"""ADR-056 accumulation screen hard-filter extract + pure first-match replay.

Canonical authority: ai-saham live predicates (structural filter then signal
assessor), first-match order. Capture may neutralize floors (all-pass
population); this module applies *counterfactual* policies for audit/replay.

Window lock: features_by_window["7"] only as the replay sample unit.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ml_saham.data.aisaham_read import connect, table_exists
from ml_saham.data.observation_cohort import (
    ACCUM_PURPOSE_LIKE,
    ACCUM_PURPOSES,
    fetch_accum_observation_raw,
    list_compatibility_cohorts,
)

# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

CANONICAL_WINDOW_KEY = "7"
ACCUM_DISCOVERY_PURPOSE = "ACCUMULATION_DISCOVERY"
ACCUM_OBSERVATION_CONTRACT = "learning_observation.accumulation_discovery.v2"

GATE_MARKET_CAP = "screen.accum.market_cap_floor"
GATE_PIOTROSKI = "screen.accum.piotroski_floor"
GATE_ACCUM_SCORE = "screen.accum.accum_score_floor"
GATE_SIGNAL_SCORE = "screen.accum.signal_score_floor"
GATE_ORDER: tuple[str, ...] = (
    GATE_MARKET_CAP,
    GATE_PIOTROSKI,
    GATE_ACCUM_SCORE,
    GATE_SIGNAL_SCORE,
)


class ScreenFilterResult(str, Enum):
    PASS = "pass"
    REJECTED_FLOW = "rejected_flow"
    REJECTED_SIGNAL = "rejected_signal"
    UNEXTRACTABLE = "unextractable_contract"


class RawInputState(str, Enum):
    NUMERIC = "numeric"
    EXPLICIT_MISSING = "explicit_missing"
    UNEXTRACTABLE = "unextractable"


@dataclass(frozen=True)
class ScreenFilterPolicy:
    """Counterfactual floors. Disabled gates are skipped (live: threshold<=0 or flag off)."""

    min_market_cap_idr: float = 0.0
    min_piotroski: float = 0.0
    min_accum_score: float = 0.0
    min_accum_score_enabled: bool = False
    min_signal_score: float = 0.0
    min_signal_score_enabled: bool = False

    def market_cap_enabled(self) -> bool:
        return self.min_market_cap_idr > 0

    def piotroski_enabled(self) -> bool:
        return self.min_piotroski > 0


@dataclass(frozen=True)
class ExtractedScreenFilterInputs:
    """Typed raw inputs for the four gates (window-7 only)."""

    ticker: str
    session_date: str
    market_cap_idr: float | None
    market_cap_state: RawInputState
    piotroski_f_score: float | None
    piotroski_state: RawInputState
    accum_score: float | None
    accum_score_state: RawInputState
    signal_score: float | None
    signal_score_state: RawInputState
    unextractable_reason: str | None = None

    @property
    def is_unextractable(self) -> bool:
        return self.unextractable_reason is not None


@dataclass(frozen=True)
class ScreenFilterClassification:
    result: ScreenFilterResult
    firing_gate: str | None = None
    reason: str | None = None


@dataclass
class ScreenFilterAuditSummary:
    compatibility_id: str
    selected_row_count: int = 0
    unique_ticker_session_count: int = 0
    extracted_count: int = 0
    unextractable_count: int = 0
    duplicate_ticker_session_count: int = 0
    wrong_purpose_skipped: int = 0
    wrong_contract_skipped: int = 0
    notes: list[str] = field(default_factory=list)
    per_gate_numeric: dict[str, int] = field(default_factory=dict)
    per_gate_explicit_missing: dict[str, int] = field(default_factory=dict)
    h10_available_count: int | None = None
    classifications: list[
        tuple[ExtractedScreenFilterInputs, ScreenFilterClassification]
    ] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure extract (payload dict)
# ---------------------------------------------------------------------------


def _window7(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    fbw = payload.get("features_by_window")
    if not isinstance(fbw, dict):
        return None
    w = fbw.get(CANONICAL_WINDOW_KEY)
    return w if isinstance(w, dict) else None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def extract_screen_filter_inputs(
    payload: Mapping[str, Any],
) -> ExtractedScreenFilterInputs:
    """Extract four gate inputs from a single ADR-056 decision payload.

    Does not invent thresholds. Missing recognized fields → explicit_missing.
    Wrong shape / missing window-7 contract → unextractable_contract.
    """
    ticker = str(payload.get("ticker") or "")
    session = str(payload.get("session_date") or "")

    if not ticker or not session:
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=None,
            market_cap_state=RawInputState.UNEXTRACTABLE,
            piotroski_f_score=None,
            piotroski_state=RawInputState.UNEXTRACTABLE,
            accum_score=None,
            accum_score_state=RawInputState.UNEXTRACTABLE,
            signal_score=None,
            signal_score_state=RawInputState.UNEXTRACTABLE,
            unextractable_reason="missing_ticker_or_session_date",
        )

    # Forbid silent root/legacy paths for canonical v2-shaped rows
    if "features_by_window" not in payload:
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=None,
            market_cap_state=RawInputState.UNEXTRACTABLE,
            piotroski_f_score=None,
            piotroski_state=RawInputState.UNEXTRACTABLE,
            accum_score=None,
            accum_score_state=RawInputState.UNEXTRACTABLE,
            signal_score=None,
            signal_score_state=RawInputState.UNEXTRACTABLE,
            unextractable_reason="missing_features_by_window",
        )

    cw = payload.get("canonical_window")
    if cw is not None and str(cw) != CANONICAL_WINDOW_KEY:
        # Still require window "7" pack as the unit
        pass

    window = _window7(payload)
    if window is None:
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=None,
            market_cap_state=RawInputState.UNEXTRACTABLE,
            piotroski_f_score=None,
            piotroski_state=RawInputState.UNEXTRACTABLE,
            accum_score=None,
            accum_score_state=RawInputState.UNEXTRACTABLE,
            signal_score=None,
            signal_score_state=RawInputState.UNEXTRACTABLE,
            unextractable_reason="missing_features_by_window.7",
        )

    candidate = window.get("candidate")
    if not isinstance(candidate, dict):
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=None,
            market_cap_state=RawInputState.UNEXTRACTABLE,
            piotroski_f_score=None,
            piotroski_state=RawInputState.UNEXTRACTABLE,
            accum_score=None,
            accum_score_state=RawInputState.UNEXTRACTABLE,
            signal_score=None,
            signal_score_state=RawInputState.UNEXTRACTABLE,
            unextractable_reason="missing_features_by_window.7.candidate",
        )

    # Market cap + Piotroski: recognized path is candidate.fundamentals
    fund = candidate.get("fundamentals")
    if fund is None:
        mcap_state = RawInputState.EXPLICIT_MISSING
        mcap_val = None
        pio_state = RawInputState.EXPLICIT_MISSING
        pio_val = None
    elif not isinstance(fund, dict):
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=None,
            market_cap_state=RawInputState.UNEXTRACTABLE,
            piotroski_f_score=None,
            piotroski_state=RawInputState.UNEXTRACTABLE,
            accum_score=None,
            accum_score_state=RawInputState.UNEXTRACTABLE,
            signal_score=None,
            signal_score_state=RawInputState.UNEXTRACTABLE,
            unextractable_reason="fundamentals_not_object",
        )
    else:
        # Key present with null = explicit missing; wrong type = unextractable
        if "market_cap_idr" not in fund:
            # Live payloads may omit the key when PIT cache has no cap — treat as explicit missing
            mcap_val = None
            mcap_state = RawInputState.EXPLICIT_MISSING
        else:
            raw_m = fund.get("market_cap_idr")
            if raw_m is None:
                mcap_val = None
                mcap_state = RawInputState.EXPLICIT_MISSING
            else:
                mcap_val = _as_float(raw_m)
                mcap_state = (
                    RawInputState.NUMERIC
                    if mcap_val is not None
                    else RawInputState.UNEXTRACTABLE
                )

        if "piotroski_f_score" not in fund:
            pio_val = None
            pio_state = RawInputState.EXPLICIT_MISSING
        else:
            raw_p = fund.get("piotroski_f_score")
            if raw_p is None:
                pio_val = None
                pio_state = RawInputState.EXPLICIT_MISSING
            else:
                pio_val = _as_float(raw_p)
                pio_state = (
                    RawInputState.NUMERIC
                    if pio_val is not None
                    else RawInputState.UNEXTRACTABLE
                )

    # Accum score
    if "accum_score" not in candidate:
        accum_val = None
        accum_state = RawInputState.UNEXTRACTABLE
        unext = "missing_candidate.accum_score"
    else:
        unext = None
        raw_a = candidate.get("accum_score")
        if raw_a is None:
            accum_val = None
            accum_state = RawInputState.EXPLICIT_MISSING
        else:
            accum_val = _as_float(raw_a)
            accum_state = (
                RawInputState.NUMERIC
                if accum_val is not None
                else RawInputState.UNEXTRACTABLE
            )
            if accum_state is RawInputState.UNEXTRACTABLE:
                unext = "unparseable_candidate.accum_score"

    # Signal score — assessment.score only (no root/legacy fallback)
    signal = window.get("signal")
    if not isinstance(signal, dict):
        sig_val = None
        sig_state = RawInputState.EXPLICIT_MISSING
        # Live assessor: assessment absent → reject when signal floor enabled.
        # Missing entire signal bag is still a recognized "assessment absent" path
        # for the enabled signal floor; extract as explicit_missing for score.
    else:
        assessment = signal.get("assessment")
        if assessment is None:
            sig_val = None
            sig_state = RawInputState.EXPLICIT_MISSING
        elif not isinstance(assessment, dict):
            sig_val = None
            sig_state = RawInputState.UNEXTRACTABLE
            unext = unext or "signal.assessment_not_object"
        elif "score" not in assessment:
            sig_val = None
            sig_state = RawInputState.EXPLICIT_MISSING
        else:
            raw_s = assessment.get("score")
            if raw_s is None:
                sig_val = None
                sig_state = RawInputState.EXPLICIT_MISSING
            else:
                sig_val = _as_float(raw_s)
                sig_state = (
                    RawInputState.NUMERIC
                    if sig_val is not None
                    else RawInputState.UNEXTRACTABLE
                )
                if sig_state is RawInputState.UNEXTRACTABLE:
                    unext = unext or "unparseable_signal.assessment.score"

    # Any unextractable field on an otherwise recognized candidate → whole row unextractable
    if (
        mcap_state is RawInputState.UNEXTRACTABLE
        or pio_state is RawInputState.UNEXTRACTABLE
        or accum_state is RawInputState.UNEXTRACTABLE
        or sig_state is RawInputState.UNEXTRACTABLE
    ):
        return ExtractedScreenFilterInputs(
            ticker=ticker,
            session_date=session,
            market_cap_idr=mcap_val,
            market_cap_state=mcap_state,
            piotroski_f_score=pio_val,
            piotroski_state=pio_state,
            accum_score=accum_val,
            accum_score_state=accum_state,
            signal_score=sig_val,
            signal_score_state=sig_state,
            unextractable_reason=unext or "unextractable_field",
        )

    return ExtractedScreenFilterInputs(
        ticker=ticker,
        session_date=session,
        market_cap_idr=mcap_val,
        market_cap_state=mcap_state,
        piotroski_f_score=pio_val,
        piotroski_state=pio_state,
        accum_score=accum_val,
        accum_score_state=accum_state,
        signal_score=sig_val,
        signal_score_state=sig_state,
        unextractable_reason=None,
    )


# ---------------------------------------------------------------------------
# Pure classifier (ai-saham semantics)
# ---------------------------------------------------------------------------


def classify_screen_filters(
    inputs: ExtractedScreenFilterInputs,
    policy: ScreenFilterPolicy,
) -> ScreenFilterClassification:
    """First-match-wins mirror of StructuralFilter then SignalAssessor floors.

    Boundary: reject when value < floor (equality passes), matching
    ``market_cap_idr < min`` / ``fscore < min`` / ``accum_score < min`` /
    ``signal score < min``.
    """
    if inputs.is_unextractable:
        return ScreenFilterClassification(
            ScreenFilterResult.UNEXTRACTABLE,
            reason=inputs.unextractable_reason,
        )

    # 1) Market-cap floor
    if policy.market_cap_enabled():
        if (
            inputs.market_cap_state is not RawInputState.NUMERIC
            or inputs.market_cap_idr is None
            or inputs.market_cap_idr < policy.min_market_cap_idr
        ):
            return ScreenFilterClassification(
                ScreenFilterResult.REJECTED_FLOW,
                firing_gate=GATE_MARKET_CAP,
                reason="market_cap_missing_or_below_floor",
            )

    # 2) Piotroski floor
    if policy.piotroski_enabled():
        if (
            inputs.piotroski_state is not RawInputState.NUMERIC
            or inputs.piotroski_f_score is None
            or inputs.piotroski_f_score < policy.min_piotroski
        ):
            return ScreenFilterClassification(
                ScreenFilterResult.REJECTED_FLOW,
                firing_gate=GATE_PIOTROSKI,
                reason="piotroski_missing_or_below_floor",
            )

    # 3) Accum score floor
    if policy.min_accum_score_enabled:
        if (
            inputs.accum_score_state is not RawInputState.NUMERIC
            or inputs.accum_score is None
            or inputs.accum_score < policy.min_accum_score
        ):
            return ScreenFilterClassification(
                ScreenFilterResult.REJECTED_FLOW,
                firing_gate=GATE_ACCUM_SCORE,
                reason="accum_score_below_floor",
            )

    # 4) Signal score floor
    if policy.min_signal_score_enabled:
        if (
            inputs.signal_score_state is not RawInputState.NUMERIC
            or inputs.signal_score is None
            or inputs.signal_score < policy.min_signal_score
        ):
            return ScreenFilterClassification(
                ScreenFilterResult.REJECTED_SIGNAL,
                firing_gate=GATE_SIGNAL_SCORE,
                reason="signal_score_missing_or_below_floor",
            )

    return ScreenFilterClassification(ScreenFilterResult.PASS, firing_gate=None)


# ---------------------------------------------------------------------------
# Cohort audit (read-only DB)
# ---------------------------------------------------------------------------


def _payload_from_row(row: Any) -> dict[str, Any] | None:
    if isinstance(row, sqlite3.Row):
        raw = row["decision_payload_json"]
    else:
        # purpose, captured_at, decision_payload_json default select
        raw = row[2] if len(row) > 2 else row[-1]
    if not isinstance(raw, str):
        return None
    try:
        obj = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def audit_screen_filter_cohort(
    db_path: Path | str,
    *,
    compatibility_id: str,
    policy: ScreenFilterPolicy | None = None,
    require_contract_id: str | None = None,
    measure_h10: bool = True,
) -> ScreenFilterAuditSummary:
    """Load one explicit ACCUM cohort and extract/classify every unique ticker/session.

    ``compatibility_id`` is required. Multi-cohort auto-select is not used.
    """
    cid = (compatibility_id or "").strip()
    if not cid:
        raise ValueError("compatibility_id is required (fail closed; no auto-select)")

    policy = policy or ScreenFilterPolicy()
    path = Path(db_path)
    summary = ScreenFilterAuditSummary(compatibility_id=cid)
    for g in GATE_ORDER:
        summary.per_gate_numeric[g] = 0
        summary.per_gate_explicit_missing[g] = 0

    with connect(path) as conn:
        if not table_exists(conn, "learning_observations"):
            summary.notes.append("learning_observations missing")
            return summary

        cohorts = list_compatibility_cohorts(
            conn, purposes=ACCUM_PURPOSES, purpose_like=ACCUM_PURPOSE_LIKE
        )
        match = next((c for c in cohorts if c[0] == cid), None)
        if match is None:
            summary.notes.append(
                f"compatibility_id={cid!r} not found among ACCUM cohorts"
            )
            return summary
        if len(cohorts) > 1:
            summary.notes.append(
                f"explicit cohort {cid[:16]}… n={match[1]}; "
                f"excluded {len(cohorts) - 1} other cohort(s)"
            )

        rows_raw, notes, resolved = fetch_accum_observation_raw(
            conn,
            preferred_compatibility_id=cid,
            compatibility_id=cid,
        )
        summary.notes.extend(notes)
        if resolved is not None and resolved != cid:
            summary.notes.append(
                f"ERROR: resolved cohort {resolved!r} != requested {cid!r}"
            )
            return summary

        seen: dict[tuple[str, str], int] = {}

        for row in rows_raw:
            if isinstance(row, sqlite3.Row):
                purpose = str(row["purpose"] or "")
            else:
                purpose = str(row[0] or "")
            if (
                purpose != ACCUM_DISCOVERY_PURPOSE
                and "ACCUMULATION_DISCOVERY" not in purpose
            ):
                if purpose not in ACCUM_PURPOSES:
                    summary.wrong_purpose_skipped += 1
                    continue

            if require_contract_id is not None and isinstance(row, sqlite3.Row):
                try:
                    crow = row["contract_id"] if "contract_id" in row.keys() else None
                except (KeyError, IndexError, TypeError):
                    crow = None
                if crow is not None and str(crow) != require_contract_id:
                    summary.wrong_contract_skipped += 1
                    continue

            payload = _payload_from_row(row)
            if payload is None:
                extracted = ExtractedScreenFilterInputs(
                    ticker="",
                    session_date="",
                    market_cap_idr=None,
                    market_cap_state=RawInputState.UNEXTRACTABLE,
                    piotroski_f_score=None,
                    piotroski_state=RawInputState.UNEXTRACTABLE,
                    accum_score=None,
                    accum_score_state=RawInputState.UNEXTRACTABLE,
                    signal_score=None,
                    signal_score_state=RawInputState.UNEXTRACTABLE,
                    unextractable_reason="invalid_decision_payload_json",
                )
            else:
                extracted = extract_screen_filter_inputs(payload)

            key = (extracted.ticker, extracted.session_date)
            seen[key] = seen.get(key, 0) + 1

            if extracted.is_unextractable:
                summary.unextractable_count += 1
            else:
                summary.extracted_count += 1
                _tally_gate(summary, GATE_MARKET_CAP, extracted.market_cap_state)
                _tally_gate(summary, GATE_PIOTROSKI, extracted.piotroski_state)
                _tally_gate(summary, GATE_ACCUM_SCORE, extracted.accum_score_state)
                _tally_gate(summary, GATE_SIGNAL_SCORE, extracted.signal_score_state)

            cls = classify_screen_filters(extracted, policy)
            summary.classifications.append((extracted, cls))

        summary.selected_row_count = len(summary.classifications)
        summary.unique_ticker_session_count = len(seen)
        summary.duplicate_ticker_session_count = sum(1 for n in seen.values() if n > 1)

        if measure_h10:
            summary.h10_available_count = _count_h10_available(
                conn, compatibility_id=cid
            )

    return summary


def _tally_gate(
    summary: ScreenFilterAuditSummary, gate: str, state: RawInputState
) -> None:
    if state is RawInputState.NUMERIC:
        summary.per_gate_numeric[gate] = summary.per_gate_numeric.get(gate, 0) + 1
    elif state is RawInputState.EXPLICIT_MISSING:
        summary.per_gate_explicit_missing[gate] = (
            summary.per_gate_explicit_missing.get(gate, 0) + 1
        )


def _count_h10_available(
    conn: sqlite3.Connection,
    *,
    compatibility_id: str,
) -> int | None:
    """Count observations in cohort with AVAILABLE price_path.accum_10d.v1 labels."""
    if not table_exists(conn, "learning_outcome_labels"):
        return None
    if not table_exists(conn, "learning_observations"):
        return None
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(learning_outcome_labels)").fetchall()
    }
    if "contract_id" not in cols or "observation_id" not in cols:
        return None
    try:
        rows = conn.execute(
            """
            SELECT COUNT(DISTINCT lol.observation_id)
            FROM learning_outcome_labels lol
            JOIN learning_observations lo ON lo.observation_id = lol.observation_id
            WHERE lo.purpose = ?
              AND lo.compatibility_id = ?
              AND lol.contract_id = 'price_path.accum_10d.v1'
              AND UPPER(COALESCE(lol.availability, '')) = 'AVAILABLE'
            """,
            (ACCUM_DISCOVERY_PURPOSE, compatibility_id),
        ).fetchone()
        return int(rows[0] or 0) if rows else 0
    except sqlite3.Error:
        return None


def sufficiency_verdict(summary: ScreenFilterAuditSummary) -> str:
    """Return SUFFICIENT_FOR_REPLAY or INSUFFICIENT_NEEDS_CORPUS_EXTENSION."""
    if summary.selected_row_count <= 0:
        return "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"
    if summary.unique_ticker_session_count <= 0:
        return "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"
    if summary.extracted_count == 0:
        return "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"
    # Schema/path failure rate: unextractable must be rare
    rate = summary.unextractable_count / max(summary.selected_row_count, 1)
    if rate > 0.05:
        return "INSUFFICIENT_NEEDS_CORPUS_EXTENSION"
    return "SUFFICIENT_FOR_REPLAY"
