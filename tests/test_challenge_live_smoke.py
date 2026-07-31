"""Optional live-DB smoke for extract hit-rates (not required for CI).

Run when a real ai-saham SQLite is available:

  export ML_SAHAM_DB=~/dev/ai-saham/data/db/data.db
  pytest tests/test_challenge_live_smoke.py -q -m live_db
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ml_saham.challenge.diagnostics.registry import load_diagnostic
from ml_saham.challenge.panel_diagnostic import (
    _mctx_from_observation,
    extract_diagnostic_features,
)
from ml_saham.challenge.panel_gates import extract_gate_components
from ml_saham.challenge.panel_iev import load_iev_raw_rows
from ml_saham.challenge.panel_screen_filters import (
    ScreenFilterPolicy,
    audit_screen_filter_cohort,
    extract_screen_filter_inputs,
    sufficiency_verdict,
)
from ml_saham.challenge.panel_signal import extract_signal_components
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.data.aisaham_read import connect
from ml_saham.data.connection import resolve_db_path
from ml_saham.data.observation_cohort import ACCUM_PURPOSES, list_compatibility_cohorts

pytestmark = pytest.mark.live_db


def _resolve_live_db() -> Path | None:
    raw = os.environ.get("ML_SAHAM_DB")
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_file() else None
    try:
        p = resolve_db_path(None)
    except Exception:
        return None
    return p if p.is_file() else None


@pytest.fixture(scope="module")
def live_db() -> Path:
    p = _resolve_live_db()
    if p is None:
        pytest.skip("no live DB (set ML_SAHAM_DB or default ai-saham path)")
    return p


def _iter_accum_payloads(db: Path, limit: int = 300):
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT decision_payload_json FROM learning_observations "
            "WHERE purpose LIKE '%ACCUM%' LIMIT ?",
            (limit,),
        ).fetchall()
    for (pj,) in rows:
        try:
            yield json.loads(pj)
        except (TypeError, json.JSONDecodeError):
            continue


def test_live_signal_extract_hit_rate(live_db: Path):
    pol = load_policy("signal.accum.raw_score")
    n = hit = 0
    for p in _iter_accum_payloads(live_db):
        n += 1
        if extract_signal_components(p, pol) is not None:
            hit += 1
    assert n >= 50, f"too few ACCUM rows: {n}"
    assert hit == n, f"signal extract miss {hit}/{n} (likely root-level path regression)"


def test_live_risk_gates_not_false_clear(live_db: Path):
    pol = load_policy("risk.accum.hard_gates")
    n = hit = blocked = 0
    for p in _iter_accum_payloads(live_db):
        c = extract_gate_components(p, pol)
        if c is None:
            continue
        hit += 1
        n += 1
        if any(v > 0 for v in c.values()):
            blocked += 1
    assert hit >= 50
    # Production corpus historically has material hard blocks; 0% is a false-clear smell
    assert blocked > 0, "block_rate_raw would be 0% — trade_setup path likely wrong"


def test_live_diagnostics_extract_hits(live_db: Path):
    for did in (
        "institutional.accumulation_bag",
        "sector.peer_context",
        "company_quality.bag",
    ):
        spec = load_diagnostic(did)
        hit = sum(
            1
            for p in _iter_accum_payloads(live_db, limit=200)
            if extract_diagnostic_features(p, spec) is not None
        )
        assert hit > 0, f"{did}: zero extractable rows on live ACCUM"


def test_live_mce_prefers_bound_context(live_db: Path):
    bound = 0
    for p in _iter_accum_payloads(live_db, limit=100):
        if _mctx_from_observation(p) is not None:
            bound += 1
    assert bound >= 50, "shared.market_context missing on live ACCUM — MCE PIT broken"


def test_live_iev_no_post_open_primary_batch(live_db: Path):
    with connect(live_db) as conn:
        rows, notes = load_iev_raw_rows(conn)
    if not rows:
        pytest.skip("no IEV history/snapshots")
    post = sum(1 for r in rows if "T09:" in str(r.get("collected_at") or ""))
    assert post == 0, f"IEV pick includes post-open captures: {post} rows; notes={notes}"


def test_live_screen_hard_filter_extract_cohort(live_db: Path):
    """Explicit compatibility_id required; extract must not silent-zero."""
    measured = "sha256:005363021f7f792071e43d12506aeefe474abf4fbd7d0a45f823b417e95e84c1"
    with connect(live_db) as conn:
        cohorts = list_compatibility_cohorts(conn, purposes=ACCUM_PURPOSES)
    if not cohorts:
        pytest.skip("no ACCUM compatibility cohorts")
    cid = measured if any(c[0] == measured for c in cohorts) else cohorts[0][0]
    if not cid:
        pytest.skip("untagged-only ACCUM cohort")

    n = hit = 0
    for p in _iter_accum_payloads(live_db, limit=200):
        n += 1
        if not extract_screen_filter_inputs(p).is_unextractable:
            hit += 1
    assert n >= 50
    assert hit == n, f"screen-filter extract miss {hit}/{n}"

    summary = audit_screen_filter_cohort(
        live_db,
        compatibility_id=cid,
        policy=ScreenFilterPolicy(),  # all disabled → pass-only classification
        measure_h10=True,
    )
    assert summary.selected_row_count > 0
    assert summary.extracted_count == summary.selected_row_count
    assert summary.unextractable_count == 0
    assert sufficiency_verdict(summary) == "SUFFICIENT_FOR_REPLAY"
