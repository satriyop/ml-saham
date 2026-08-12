"""Proposal-only hard-filter discovery panel and train-only thresholds."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date, timedelta

import pytest

from ml_saham.challenge.panel_screen_filters import extract_screen_filter_inputs
from ml_saham.challenge.screen_filter_discovery import (
    DISCOVERY_EVIDENCE_NO_SELECTION,
    NOT_READY_GEOMETRY,
    ScreenFilterDiscoveryPanel,
    ScreenFilterDiscoveryRow,
    _strict_h10_excess,
    evaluate_screen_filter_discovery,
    run_screen_filter_discovery,
)
from ml_saham.challenge.screen_filter_preregistration import (
    build_screen_filter_preregistration,
)
from tests.fixtures.golden import load_golden


def _inputs(value: float, ticker: str, session: str):
    return extract_screen_filter_inputs(
        {
            "ticker": ticker,
            "session_date": session,
            "canonical_window": 7,
            "features_by_window": {
                "7": {
                    "candidate": {
                        "accum_score": value,
                        "fundamentals": {
                            "market_cap_idr": value * 1e12,
                            "piotroski_f_score": value,
                        },
                    },
                    "signal": {"assessment": {"score": value}},
                }
            },
        }
    )


def _panel(*, mutate_late_test_values: bool = False) -> ScreenFilterDiscoveryPanel:
    rows: list[ScreenFilterDiscoveryRow] = []
    start = date(2026, 1, 1)
    for session_index in range(64):
        session = (start + timedelta(days=session_index)).isoformat()
        for ticker_index in range(45):
            value = float(ticker_index + 1)
            if mutate_late_test_values and session_index >= 32:
                value += 10_000.0
            rows.append(
                ScreenFilterDiscoveryRow(
                    ticker=f"T{ticker_index:02d}",
                    date=session,
                    inputs=_inputs(value, f"T{ticker_index:02d}", session),
                    h10_excess=(ticker_index - 22) / 1000.0,
                )
            )
    return ScreenFilterDiscoveryPanel(
        compatibility_id="sha256:" + "ab" * 32,
        rows=tuple(rows),
        selected_units=len(rows),
        label_unavailable_units=0,
        unextractable_units=0,
        duplicate_units=0,
    )


def test_discovery_reports_every_variant_without_winner_or_selection():
    result = evaluate_screen_filter_discovery(_panel())

    assert result.status == DISCOVERY_EVIDENCE_NO_SELECTION
    assert result.folds_formed == 2
    assert result.selected_candidate is None
    assert result.winner is None
    assert result.selected_units == 64 * 45
    assert result.n_panel_rows == result.selected_units
    assert result.panel_digest.startswith("sha256:")
    assert replace(_panel(), rows=tuple(reversed(_panel().rows))).content_digest == (
        _panel().content_digest
    )
    assert len(result.variants) == 4 * 3 * 2
    assert all(item.support_ok for item in result.variants)
    assert all(item.embargo_sessions_actual >= 20 for item in result.variants)
    assert {
        item.decision_quality["contract_id"] for item in result.variants
    } == {"gate_decision_quality.v1"}


def test_test_only_value_mutation_cannot_change_train_fitted_thresholds():
    original = evaluate_screen_filter_discovery(_panel())
    mutated = evaluate_screen_filter_discovery(_panel(mutate_late_test_values=True))

    before = [
        (item.gate_id, item.quantile, item.fold_index, item.threshold)
        for item in original.variants
    ]
    after = [
        (item.gate_id, item.quantile, item.fold_index, item.threshold)
        for item in mutated.variants
    ]
    assert after == before
    assert mutated.panel_digest != original.panel_digest


def test_thin_calendar_returns_not_ready_without_partial_proposals():
    thin = replace(_panel(), rows=_panel().rows[: 25 * 45], selected_units=25 * 45)
    result = evaluate_screen_filter_discovery(thin)
    assert result.status == NOT_READY_GEOMETRY
    assert result.folds_formed == 0
    assert result.variants == ()
    assert result.winner is None


def test_golden_strict_h10_uses_identical_stock_and_benchmark_end_session():
    golden = load_golden("accum_screen_hard_filter_discovery.json")
    extracted = extract_screen_filter_inputs(golden["observation"])
    assert not extracted.is_unextractable

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE candles (ticker TEXT, date TEXT, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL)"
    )
    start = date(2026, 6, 1)
    sessions = [(start + timedelta(days=i)).isoformat() for i in range(11)]
    for index, session in enumerate(sessions):
        conn.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
            ("IHSG", session, 0, 0, 0, 7000 + 14 * index, 1),
        )
        conn.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
            ("PRBA", session, 0, 0, 0, 100 + index, 1),
        )
    excess = _strict_h10_excess(conn, (("PRBA", sessions[0]),))
    assert excess[("PRBA", sessions[0])] == pytest.approx(
        golden["expect"]["h10_excess"]
    )

    conn.execute("DELETE FROM candles WHERE ticker='PRBA' AND date=?", (sessions[10],))
    assert _strict_h10_excess(conn, (("PRBA", sessions[0]),)) == {}

    conn.execute(
        "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
        ("IHSG", sessions[0], 0, 0, 0, 7000, 1),
    )
    with pytest.raises(ValueError, match="duplicate candle key"):
        _strict_h10_excess(conn, (("PRBA", sessions[0]),))


def test_preregistration_remains_discovery_only():
    prereg = build_screen_filter_preregistration()
    assert prereg.engine_registration_authorized is False
    assert prereg.discovery_outcome == "proposal_only_no_win_lose"


def test_missing_explicit_cohort_blocks_before_database_access():
    result = run_screen_filter_discovery("does-not-exist.db", compatibility_id="")
    assert result.status == "BLOCKED_POLICY"
    assert result.panel_digest == ""
    assert result.winner is None


def test_incomplete_gate_matrix_fails_closed_instead_of_claiming_discovery():
    panel = _panel()
    rows = tuple(
        replace(
            row,
            inputs=replace(
                row.inputs,
                market_cap_idr=0.0,
                market_cap_state=row.inputs.market_cap_state,
            ),
        )
        for row in panel.rows
    )
    result = evaluate_screen_filter_discovery(replace(panel, rows=rows))
    assert result.status == "BLOCKED_DATA"
    assert any("incomplete discovery matrix" in note for note in result.notes)
    assert result.winner is None
