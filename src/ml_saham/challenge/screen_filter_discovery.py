"""Proposal-only C2 hard-filter discovery over strict H10 excess labels.

No function in this module emits WIN/LOSE, chooses a winner, registers a
PolicySpec, or writes an artifact. Thresholds are fit from each train fold's
finite numeric inputs and then applied unchanged to that fold's OOS rows.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Sequence

from ml_saham.challenge.metrics import Fold, time_purged_folds
from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.panel_gates import GatePanelRow
from ml_saham.challenge.panel_screen_filters import (
    ACCUM_DISCOVERY_PURPOSE,
    ACCUM_OBSERVATION_CONTRACT,
    GATE_ACCUM_SCORE,
    GATE_MARKET_CAP,
    GATE_ORDER,
    GATE_PIOTROSKI,
    GATE_SIGNAL_SCORE,
    ExtractedScreenFilterInputs,
    RawInputState,
    ScreenFilterPolicy,
    ScreenFilterResult,
    _payload_from_row,
    classify_screen_filters,
    extract_screen_filter_inputs,
    fetch_observation_discovery_only,
)
from ml_saham.challenge.policies.registry import load_policy_adapter
from ml_saham.challenge.production_policy_snapshots import (
    PolicySnapshotError,
    compose_execution_policy,
    load_verified_snapshot_set,
)
from ml_saham.challenge.protocols import ACCUM_PATH_V1
from ml_saham.challenge.scorers import gate_decision_quality
from ml_saham.challenge.screen_filter_preregistration import (
    ScreenFilterPreregistration,
    build_screen_filter_preregistration,
)
from ml_saham.data.aisaham_read import connect, load_candles, table_exists

SCREEN_FILTER_DISCOVERY_CONTRACT_ID = "screen_accum_hard_filters.discovery.v1"

DISCOVERY_EVIDENCE_NO_SELECTION = "DISCOVERY_EVIDENCE_NO_SELECTION"
NOT_READY_GEOMETRY = "NOT_READY_GEOMETRY"
BLOCKED_DATA = "BLOCKED_DATA"
BLOCKED_POLICY = "BLOCKED_POLICY"


class ScreenFilterDiscoveryDataError(ValueError):
    """Malformed or conflicting candle material; never ordinary missingness."""


@dataclass(frozen=True)
class ScreenFilterDiscoveryRow:
    ticker: str
    date: str
    inputs: ExtractedScreenFilterInputs
    h10_excess: float

    def panel_row(self) -> PanelRow:
        return PanelRow(
            ticker=self.ticker,
            date=self.date,
            components={},
            excess={10: self.h10_excess},
        )


@dataclass(frozen=True)
class ScreenFilterDiscoveryPanel:
    compatibility_id: str
    rows: tuple[ScreenFilterDiscoveryRow, ...]
    selected_units: int
    label_unavailable_units: int
    unextractable_units: int
    duplicate_units: int
    notes: tuple[str, ...] = ()

    @property
    def content_digest(self) -> str:
        material = [
            {
                "ticker": row.ticker,
                "date": row.date,
                "market_cap_idr": row.inputs.market_cap_idr,
                "market_cap_state": row.inputs.market_cap_state.value,
                "piotroski_f_score": row.inputs.piotroski_f_score,
                "piotroski_state": row.inputs.piotroski_state.value,
                "accum_score": row.inputs.accum_score,
                "accum_score_state": row.inputs.accum_score_state.value,
                "signal_score": row.inputs.signal_score,
                "signal_score_state": row.inputs.signal_score_state.value,
                "h10_excess": row.h10_excess,
            }
            for row in sorted(self.rows, key=lambda item: (item.date, item.ticker))
        ]
        canonical = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScreenFilterDiscoveryFoldEvidence:
    gate_id: str
    quantile: float
    fold_index: int
    threshold: float
    n_train: int
    n_test: int
    n_train_numeric: int
    n_allowed: int
    n_rejected: int
    support_ok: bool
    train_date_max: str | None
    test_date_min: str | None
    test_date_max: str | None
    embargo_sessions_actual: int
    decision_quality: dict[str, object]


@dataclass(frozen=True)
class ScreenFilterDiscoveryResult:
    contract_id: str
    preregistration_contract_id: str
    methodology_digest: str
    compatibility_id: str
    panel_digest: str
    status: str
    selected_units: int
    n_panel_rows: int
    label_unavailable_units: int
    unextractable_units: int
    duplicate_units: int
    n_sessions: int
    folds_formed: int
    min_valid_oos_folds: int
    variants: tuple[ScreenFilterDiscoveryFoldEvidence, ...] = ()
    selected_candidate: None = None
    winner: None = None
    notes: tuple[str, ...] = ()


def _strict_h10_excess(
    conn: sqlite3.Connection,
    keys: Sequence[tuple[str, str]],
) -> dict[tuple[str, str], float]:
    """H10 stock-IHSG return using the exact same start and end sessions."""

    tickers = sorted({ticker for ticker, _date in keys})
    candles = load_candles(conn, [*tickers, "IHSG"])
    closes: dict[str, dict[str, float]] = {}
    for row in candles:
        ticker = str(row["ticker"])
        date = str(row["date"])
        try:
            close = float(row["close"])
        except (TypeError, ValueError) as exc:
            raise ScreenFilterDiscoveryDataError(
                f"malformed candle close ticker={ticker!r} date={date!r}"
            ) from exc
        if not math.isfinite(close) or close <= 0:
            raise ScreenFilterDiscoveryDataError(
                f"invalid candle close ticker={ticker!r} date={date!r}"
            )
        if date in closes.get(ticker, {}):
            raise ScreenFilterDiscoveryDataError(
                f"duplicate candle key ticker={ticker!r} date={date!r}"
            )
        closes.setdefault(ticker, {})[date] = close

    ihsg = closes.get("IHSG", {})
    sessions = sorted(ihsg)
    index = {date: i for i, date in enumerate(sessions)}
    out: dict[tuple[str, str], float] = {}
    for ticker, start in keys:
        i = index.get(start)
        if i is None or i + 10 >= len(sessions):
            continue
        end = sessions[i + 10]
        stock = closes.get(ticker, {})
        if start not in stock or end not in stock:
            continue
        stock_return = stock[end] / stock[start] - 1.0
        benchmark_return = ihsg[end] / ihsg[start] - 1.0
        excess = stock_return - benchmark_return
        if math.isfinite(excess):
            out[(ticker, start)] = excess
    return out


def load_screen_filter_discovery_panel(
    db_path: Path | str,
    *,
    compatibility_id: str,
) -> tuple[ScreenFilterDiscoveryPanel | None, str | None, tuple[str, ...]]:
    """Load one verified cohort and strict H10 excess labels, read-only."""

    cid = (compatibility_id or "").strip()
    if not cid:
        return None, BLOCKED_POLICY, ("explicit compatibility_id is required",)

    path = Path(db_path)
    notes: list[str] = []
    with connect(path) as conn:
        try:
            snapshots = load_verified_snapshot_set(conn, cid)
            adapter = load_policy_adapter("screener.accum.hard_filters")
            compose_execution_policy(
                snapshots["screener.accum.hard_filters"], adapter
            )
        except (KeyError, PolicySnapshotError, ValueError) as exc:
            return None, BLOCKED_POLICY, (str(exc),)

        if not table_exists(conn, "learning_observations"):
            return None, BLOCKED_DATA, ("learning_observations missing",)

        rows_raw, cohort_notes, resolved = fetch_observation_discovery_only(
            conn,
            compatibility_id=cid,
            select=(
                "purpose, captured_at, decision_payload_json, contract_id, "
                "observation_id"
            ),
        )
        notes.extend(cohort_notes)
        if resolved != cid:
            return None, BLOCKED_POLICY, (
                *notes,
                f"resolved compatibility_id={resolved!r} does not match {cid!r}",
            )

        by_key: dict[tuple[str, str], ExtractedScreenFilterInputs] = {}
        duplicates = 0
        unextractable = 0
        for row in rows_raw:
            purpose = str(row["purpose"] or "")
            contract = str(row["contract_id"] or "")
            observation_id = str(row["observation_id"] or "")
            if purpose != ACCUM_DISCOVERY_PURPOSE or contract != ACCUM_OBSERVATION_CONTRACT:
                unextractable += 1
                continue
            payload = _payload_from_row(row)
            if payload is None or not observation_id:
                unextractable += 1
                continue
            inputs = extract_screen_filter_inputs(payload)
            if inputs.is_unextractable:
                unextractable += 1
                continue
            ticker = inputs.ticker
            session_date = inputs.session_date
            try:
                parsed_date = Date.fromisoformat(session_date)
            except ValueError:
                parsed_date = None
            if (
                ticker != ticker.strip().upper()
                or parsed_date is None
                or parsed_date.isoformat() != session_date
            ):
                unextractable += 1
                continue
            key = (ticker, session_date)
            if key in by_key:
                duplicates += 1
                continue
            by_key[key] = inputs

        if unextractable or duplicates:
            return None, BLOCKED_DATA, (
                *notes,
                "discovery population must reconcile exactly: "
                f"unextractable={unextractable} duplicates={duplicates}",
            )
        if not by_key:
            return None, BLOCKED_DATA, (*notes, "no extractable discovery units")

        try:
            excess = _strict_h10_excess(conn, tuple(by_key))
        except ScreenFilterDiscoveryDataError as exc:
            return None, BLOCKED_DATA, (*notes, str(exc))
        labeled = tuple(
            ScreenFilterDiscoveryRow(
                ticker=ticker,
                date=date,
                inputs=inputs,
                h10_excess=excess[(ticker, date)],
            )
            for (ticker, date), inputs in sorted(by_key.items())
            if (ticker, date) in excess
        )
        unavailable = len(by_key) - len(labeled)
        panel = ScreenFilterDiscoveryPanel(
            compatibility_id=cid,
            rows=labeled,
            selected_units=len(by_key),
            label_unavailable_units=unavailable,
            unextractable_units=unextractable,
            duplicate_units=duplicates,
            notes=tuple(notes),
        )
        if not labeled:
            return panel, BLOCKED_DATA, (*notes, "no strict H10 excess labels")
        return panel, None, tuple(notes)


def _numeric_gate_value(
    inputs: ExtractedScreenFilterInputs,
    gate_id: str,
) -> float | None:
    fields = {
        GATE_MARKET_CAP: (inputs.market_cap_state, inputs.market_cap_idr),
        GATE_PIOTROSKI: (inputs.piotroski_state, inputs.piotroski_f_score),
        GATE_ACCUM_SCORE: (inputs.accum_score_state, inputs.accum_score),
        GATE_SIGNAL_SCORE: (inputs.signal_score_state, inputs.signal_score),
    }
    state, value = fields[gate_id]
    if state is not RawInputState.NUMERIC or value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _linear_quantile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("cannot fit threshold without finite train values")
    position = (len(ordered) - 1) * quantile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _single_gate_policy(gate_id: str, threshold: float) -> ScreenFilterPolicy:
    kwargs: dict[str, object] = {}
    if gate_id == GATE_MARKET_CAP:
        kwargs["min_market_cap_idr"] = threshold
    elif gate_id == GATE_PIOTROSKI:
        kwargs["min_piotroski"] = threshold
    elif gate_id == GATE_ACCUM_SCORE:
        kwargs.update(
            min_accum_score=threshold,
            min_accum_score_enabled=True,
        )
    elif gate_id == GATE_SIGNAL_SCORE:
        kwargs.update(
            min_signal_score=threshold,
            min_signal_score_enabled=True,
        )
    else:
        raise ValueError(f"unknown hard-filter gate_id={gate_id!r}")
    return ScreenFilterPolicy(**kwargs)


def _evaluate_variant_fold(
    rows: Sequence[ScreenFilterDiscoveryRow],
    fold: Fold,
    *,
    gate_id: str,
    quantile: float,
    fold_index: int,
    preregistration: ScreenFilterPreregistration,
) -> ScreenFilterDiscoveryFoldEvidence | None:
    train_values = [
        value
        for index in fold.train_idx
        if (value := _numeric_gate_value(rows[index].inputs, gate_id)) is not None
    ]
    if not train_values:
        return None
    threshold = _linear_quantile(train_values, quantile)
    if gate_id in (GATE_MARKET_CAP, GATE_PIOTROSKI) and threshold <= 0:
        return None
    policy = _single_gate_policy(gate_id, threshold)

    quality_rows: list[GatePanelRow] = []
    allow_scores: list[float] = []
    for index in fold.test_idx:
        row = rows[index]
        classification = classify_screen_filters(row.inputs, policy)
        if classification.result is ScreenFilterResult.UNEXTRACTABLE:
            raise ValueError("prevalidated discovery row became unextractable")
        rejected = classification.result is not ScreenFilterResult.PASS
        components = {gate_id: 1.0 if rejected else 0.0}
        blockers = (gate_id,) if rejected else ()
        quality_rows.append(
            GatePanelRow(
                ticker=row.ticker,
                date=row.date,
                components=components,
                excess={10: row.h10_excess},
                ordered_blockers=blockers,
            )
        )
        allow_scores.append(0.0 if rejected else 1.0)

    quality = gate_decision_quality(
        quality_rows,
        allow_scores,
        10,
        active_gate_keys=(gate_id,),
    )
    n_allowed = int(quality["allowed_book"]["n"])
    n_rejected = int(quality["blocked_book"]["n"])
    side_floor = preregistration.min_per_side_labeled_rows_per_fold
    return ScreenFilterDiscoveryFoldEvidence(
        gate_id=gate_id,
        quantile=quantile,
        fold_index=fold_index,
        threshold=threshold,
        n_train=len(fold.train_idx),
        n_test=len(fold.test_idx),
        n_train_numeric=len(train_values),
        n_allowed=n_allowed,
        n_rejected=n_rejected,
        support_ok=n_allowed >= side_floor and n_rejected >= side_floor,
        train_date_max=fold.train_date_max,
        test_date_min=fold.test_date_min,
        test_date_max=fold.test_date_max,
        embargo_sessions_actual=fold.embargo_sessions_actual,
        decision_quality=quality,
    )


def evaluate_screen_filter_discovery(
    panel: ScreenFilterDiscoveryPanel,
    *,
    preregistration: ScreenFilterPreregistration | None = None,
) -> ScreenFilterDiscoveryResult:
    """Evaluate all preregistered variants without ranking or selection."""

    prereg = preregistration or build_screen_filter_preregistration()
    rows = tuple(panel.rows)
    keys = [(row.ticker, row.date) for row in rows]
    if not panel.compatibility_id.strip():
        raise ValueError("discovery panel compatibility_id is required")
    if len(set(keys)) != len(keys):
        raise ValueError("discovery panel contains duplicate ticker/session units")
    if panel.unextractable_units or panel.duplicate_units:
        raise ValueError("discovery panel contains unreconciled excluded units")
    if panel.selected_units != len(rows) + panel.label_unavailable_units:
        raise ValueError("discovery panel selected/labeled denominator mismatch")
    for row in rows:
        if (row.inputs.ticker, row.inputs.session_date) != (row.ticker, row.date):
            raise ValueError("discovery panel row/input identity mismatch")
        if not math.isfinite(row.h10_excess):
            raise ValueError("discovery panel H10 excess must be finite")
    panel_rows = [row.panel_row() for row in rows]
    folds = time_purged_folds(panel_rows, ACCUM_PATH_V1)
    notes = list(panel.notes)
    if len(folds) < prereg.min_valid_oos_folds:
        notes.append(
            f"folds_formed={len(folds)} < "
            f"min_valid_oos_folds={prereg.min_valid_oos_folds}"
        )
        return ScreenFilterDiscoveryResult(
            contract_id=SCREEN_FILTER_DISCOVERY_CONTRACT_ID,
            preregistration_contract_id=prereg.contract_id,
            methodology_digest=prereg.methodology_digest,
            compatibility_id=panel.compatibility_id,
            panel_digest=panel.content_digest,
            status=NOT_READY_GEOMETRY,
            selected_units=panel.selected_units,
            n_panel_rows=len(rows),
            label_unavailable_units=panel.label_unavailable_units,
            unextractable_units=panel.unextractable_units,
            duplicate_units=panel.duplicate_units,
            n_sessions=len({row.date for row in rows}),
            folds_formed=len(folds),
            min_valid_oos_folds=prereg.min_valid_oos_folds,
            notes=tuple(notes),
        )

    evidence: list[ScreenFilterDiscoveryFoldEvidence] = []
    for gate_id in prereg.gate_order:
        for quantile in prereg.discovery_quantile_grid:
            for fold_index, fold in enumerate(folds):
                item = _evaluate_variant_fold(
                    rows,
                    fold,
                    gate_id=gate_id,
                    quantile=quantile,
                    fold_index=fold_index,
                    preregistration=prereg,
                )
                if item is not None:
                    evidence.append(item)
                else:
                    notes.append(
                        f"gate={gate_id} q={quantile}: no finite train values"
                    )

    expected_evidence = (
        len(prereg.gate_order) * len(prereg.discovery_quantile_grid) * len(folds)
    )
    status = (
        DISCOVERY_EVIDENCE_NO_SELECTION
        if len(evidence) == expected_evidence
        else BLOCKED_DATA
    )
    if status == BLOCKED_DATA:
        notes.append(
            f"incomplete discovery matrix evidence={len(evidence)} "
            f"expected={expected_evidence}"
        )
    return ScreenFilterDiscoveryResult(
        contract_id=SCREEN_FILTER_DISCOVERY_CONTRACT_ID,
        preregistration_contract_id=prereg.contract_id,
        methodology_digest=prereg.methodology_digest,
        compatibility_id=panel.compatibility_id,
        panel_digest=panel.content_digest,
        status=status,
        selected_units=panel.selected_units,
        n_panel_rows=len(rows),
        label_unavailable_units=panel.label_unavailable_units,
        unextractable_units=panel.unextractable_units,
        duplicate_units=panel.duplicate_units,
        n_sessions=len({row.date for row in rows}),
        folds_formed=len(folds),
        min_valid_oos_folds=prereg.min_valid_oos_folds,
        variants=tuple(evidence),
        notes=tuple(notes),
    )


def run_screen_filter_discovery(
    db_path: Path | str,
    *,
    compatibility_id: str,
) -> ScreenFilterDiscoveryResult:
    """Read-only composition boundary for proposal-only discovery."""

    prereg = build_screen_filter_preregistration()
    panel, blocked, notes = load_screen_filter_discovery_panel(
        db_path,
        compatibility_id=compatibility_id,
    )
    if panel is None or blocked is not None:
        return ScreenFilterDiscoveryResult(
            contract_id=SCREEN_FILTER_DISCOVERY_CONTRACT_ID,
            preregistration_contract_id=prereg.contract_id,
            methodology_digest=prereg.methodology_digest,
            compatibility_id=(compatibility_id or "").strip(),
            panel_digest=panel.content_digest if panel is not None else "",
            status=blocked or BLOCKED_DATA,
            selected_units=panel.selected_units if panel is not None else 0,
            n_panel_rows=len(panel.rows) if panel is not None else 0,
            label_unavailable_units=(
                panel.label_unavailable_units if panel is not None else 0
            ),
            unextractable_units=(
                panel.unextractable_units if panel is not None else 0
            ),
            duplicate_units=panel.duplicate_units if panel is not None else 0,
            n_sessions=(
                len({row.date for row in panel.rows}) if panel is not None else 0
            ),
            folds_formed=0,
            min_valid_oos_folds=prereg.min_valid_oos_folds,
            notes=notes,
        )
    return evaluate_screen_filter_discovery(panel, preregistration=prereg)
