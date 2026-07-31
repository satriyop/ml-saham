"""Payload / invariant contracts for product challenge extracts.

Golden fixtures under tests/fixtures/golden/ are live-shaped (ADR-056, open_30m,
NCP IEV). These tests call **shipped** helpers — not re-implemented parsers.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from ml_saham.challenge.panel import extract_components
from ml_saham.challenge.panel_iev import (
    _component_features,
    _pick_history_batches,
)
from ml_saham.challenge.panel_pre_open_obs import (
    _pct_points_to_fraction,
    _stock_open_to_0930_return,
)
from ml_saham.challenge.panel_gates import extract_gate_components
from ml_saham.challenge.panel_signal import extract_signal_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.challenge.protocols import ACCUM_PATH_V1, PRE_OPEN_SESSION_V1
from ml_saham.challenge.runner import _verdict
from ml_saham.challenge.types import ChallengeStatus
from tests.fixtures.golden import golden_path, load_golden

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def test_golden_files_exist_in_repo():
    required = (
        "accum_adr056_window.json",
        "signal_adr056_window.json",
        "open_30m_metrics.json",
        "iev_multi_capture_day.json",
        "risk_adr056_trade_setup.json",
        "README.md",
    )
    for name in required:
        assert golden_path(name).is_file(), name
    # Must not be the only source of truth: goldens live outside build_mvp_fixture
    assert not str(GOLDEN_DIR).endswith("build_mvp_fixture.py")


# --- (c) Signal score path: features_by_window, not top-level signal.raw_score ---


def test_signal_extract_from_golden_adr056_window_not_top_level():
    payload = load_golden("signal_adr056_window.json")
    assert "signal" not in payload or not payload.get("signal")
    pol = load_policy("signal.accum.raw_score")
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    # live order prefers raw_exact_score over assessment.score
    assert comps["production_raw_score"] == pytest.approx(55.29)
    # wrong path (top-level only) would return None
    broken = {"signal": {}}
    assert extract_signal_components(broken, pol) is None


def test_signal_flags_from_window_active_flags():
    payload = load_golden("signal_adr056_window.json")
    pol = load_policy("signal.accum.flags")
    comps = extract_signal_components(payload, pol)
    assert comps is not None
    assert comps["production_raw_score"] == pytest.approx(55.29)
    assert comps["valuation_stretched"] == 1.0


def test_risk_gates_from_window_trade_setup_not_top_level():
    """Live ACCUM risk is under features_by_window.*.trade_setup — root path is false-clear."""
    payload = load_golden("risk_adr056_trade_setup.json")
    pol = load_policy("risk.accum.hard_gates")
    comps = extract_gate_components(payload, pol)
    assert comps is not None
    assert comps["bandar_gate"] == 1.0
    assert comps["free_float_gate"] == 1.0
    # Root-only empty would previously report all zeros (false clear)
    root_empty = {"trade_setup": {}}
    assert extract_gate_components(root_empty, pol) is None


def test_accum_sleeves_from_golden_adr056_prefers_canonical_window():
    payload = load_golden("accum_adr056_window.json")
    pol = load_policy("screener.accum.score_weights")
    comps = extract_components(payload, pol)
    assert comps is not None
    assert comps["consistency"] == 9.5
    # window 30 has cons=99 — must not win over canonical 7
    assert comps["consistency"] != 99.0


# --- (a) Pre-open label units + same-horizon invariant ---


def test_open_30m_return_pct_is_percent_points_not_fraction():
    g = load_golden("open_30m_metrics.json")
    m = g["metrics"]
    # price path
    r = _stock_open_to_0930_return(m)
    assert r == pytest.approx(161.0 / 162.0 - 1.0)
    assert abs(r) < 0.02  # not -0.6173

    # pct-only: the historic bug treated |x|<=1 as fraction
    r2 = _stock_open_to_0930_return(g["metrics_pct_only"])
    assert r2 == pytest.approx(-0.006173)
    assert r2 != pytest.approx(-0.6173)

    r3 = _pct_points_to_fraction(g["metrics_large_move_pct"]["open_to_close_return_pct"])
    assert r3 == pytest.approx(-0.013333)


def test_no_old_abs_le_one_fraction_heuristic_in_product_pre_open():
    """Source guard: product path must not reintroduce |x|<=1 ⇒ fraction."""
    src = Path("src/ml_saham/challenge/panel_pre_open_obs.py").read_text(encoding="utf-8")
    assert "abs(x) > 1" not in src
    assert "abs(x) <= 1" not in src
    assert "_pct_points_to_fraction" in src
    # conversion is always / 100
    assert "/ 100" in src or "/100" in src


def test_pre_open_label_notes_forbid_mixed_horizon_benchmark():
    """Documented invariant: open_30m stock path is gross, not full-day IHSG excess."""
    src = Path("src/ml_saham/challenge/panel_pre_open_obs.py").read_text(encoding="utf-8")
    assert "Do **not** subtract full-session IHSG" in src or "not excess vs full-day IHSG" in src
    assert "open_30m" in src


# --- (b) IEV NCP batch + no curriculum iev/iep ratio ---


def test_iev_golden_batch_prefers_ncp_preopen_not_largest_post_open():
    rows = load_golden("iev_multi_capture_day.json")["rows"]
    picked, notes = _pick_history_batches(rows)
    assert {r["ticker"] for r in picked} == {"AAA", "BBB"}
    assert all(r["collected_at"] == "2024-06-17T08:56:04" for r in picked)
    # largest post-open had CCC + huge iev — must not be selected
    assert all(r["collected_at"] != "2024-06-17T09:08:29" for r in picked)
    assert any("NCP" in n or "pre-open" in n.lower() or "ncp" in n.lower() for n in notes)


def test_product_iev_features_have_no_volume_over_price_imbalance():
    comps = _component_features(iev=1_602_630.0, iep=165.0, rank=1, max_rank=50)
    assert "imbalance" not in comps
    assert comps["log_iev"] == pytest.approx(math.log1p(1_602_630.0))
    # curriculum bug magnitude
    assert comps["log_iev"] < 20
    pol = load_policy("screener.pre_open.iev_rank")
    keys = {c.key for c in pol.components}
    assert "imbalance" not in keys
    assert "log_iev" in keys


def test_product_panel_iev_source_forbids_iev_over_iep_assignment():
    src = Path("src/ml_saham/challenge/panel_iev.py").read_text(encoding="utf-8")
    # No live ratio assignment (docstring may mention the forbidden form)
    assert "iev / iep - 1.0" not in src
    assert "iev/iep - 1.0" not in src
    assert "(iev / iep" not in src
    assert "log1p" in src and "log_iev" in src


# --- (4) Verdict = evidence shape ---


def test_protocols_require_min_folds_for_win():
    assert ACCUM_PATH_V1.min_folds_for_win >= 2
    assert PRE_OPEN_SESSION_V1.min_folds_for_win >= 2


def test_single_fold_ic_edge_provisional_not_win():
    status, _, _, notes = _verdict(
        ACCUM_PATH_V1,
        [{"ic_baseline": 0.01, "ic_against": 0.10, "tail_baseline": 0.0, "tail_against": 0.0}],
        baseline_id="production",
        against_id="equal_sleeves",
    )
    assert status == ChallengeStatus.INCONCLUSIVE
    assert any("provisional" in n.lower() for n in notes)
