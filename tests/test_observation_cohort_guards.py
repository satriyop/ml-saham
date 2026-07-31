"""Guards that stop silent multi-cohort loads and retired-table SSOT regressions."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from ml_saham.challenge.panel import build_panel
from ml_saham.challenge.policies.registry import load_policy
from ml_saham.data.doctor_checks import run_doctor
from ml_saham.data.observation_cohort import (
    fetch_accum_observation_raw,
    list_compatibility_cohorts,
)
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ml_saham"

# Challenge modules may only query learning_observations via observation_cohort.
_ALLOWED_LEARNING_OBS_SQL_FILES = {
    "data/observation_cohort.py",
    # doctor counts / join integrity (not panel feature loads)
    "data/doctor_checks.py",
}

_RETIRED_TABLES = ("candidate_observations", "signal_forward_labels")
# Files allowed to mention retired names (docs, fallbacks, comments).
_RETIRED_ALLOWLIST = {
    "data/phase2_read.py",  # soft legacy fallback only
    "data/doctor_checks.py",  # warn if present, never ok
}


def _rel(path: Path) -> str:
    return str(path.relative_to(SRC)).replace("\\", "/")


def test_mvp_fixture_has_two_accum_cohorts_and_panel_uses_largest(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "dual.db", min_bars=100)
    from ml_saham.data.aisaham_read import connect

    with connect(db) as conn:
        cohorts = list_compatibility_cohorts(
            conn,
            purposes=("ACCUMULATION_DISCOVERY",),
            purpose_like=("%ACCUM%",),
        )
        assert len(cohorts) >= 2
        assert cohorts[0][0] == "sha256:fixture_cohort_primary"
        assert cohorts[0][1] > cohorts[1][1]

        rows, notes, resolved = fetch_accum_observation_raw(conn)
        assert resolved == "sha256:fixture_cohort_primary"
        assert any("auto-selected largest" in n or "single cohort" in n for n in notes)
        # Secondary cohort markers must not appear
        for r in rows:
            payload = r["decision_payload_json"] if hasattr(r, "keys") else r[2]
            assert "fixture_cohort_secondary" not in str(payload)
            assert "obs-small-" not in str(
                r["observation_id"] if hasattr(r, "keys") and "observation_id" in r.keys() else ""
            )

    pol = load_policy("screener.accum.score_weights")
    panel_rows, panel_notes = build_panel(
        db, pol, horizons=(3, 10, 20), primary_horizon=10
    )
    assert panel_rows, panel_notes
    assert any("compatibility_id" in n for n in panel_notes)
    # raw_score 99.0 only exists on secondary tiny cohort rows
    assert all(
        not (
            abs(r.components.get("consistency", 0) - 99.0) < 1e-6
            and abs(r.components.get("streak", 0) - 99.0) < 1e-6
        )
        for r in panel_rows
    )


def test_doctor_reports_multi_cohort_partial(tmp_path: Path):
    db = build_mvp_fixture(tmp_path / "doc.db", min_bars=80)
    report = run_doctor(db, deep=True)
    names = {i.name: i for i in report.integrity.items}
    assert "compatibility_cohorts_accum" in names
    item = names["compatibility_cohorts_accum"]
    assert item.status in ("ok", "partial")
    if item.status == "partial":
        assert "never mixes" in item.detail or "largest" in item.detail


def test_no_raw_learning_observations_sql_outside_cohort_module():
    """Challenge + chapters must not invent purpose-only observation loads."""
    offenders: list[str] = []
    pattern = re.compile(
        r"FROM\s+learning_observations",
        re.IGNORECASE,
    )
    for path in SRC.rglob("*.py"):
        rel = _rel(path)
        if rel in _ALLOWED_LEARNING_OBS_SQL_FILES:
            continue
        # phase2_read does not select observations table for panels
        text = path.read_text(encoding="utf-8")
        if not pattern.search(text):
            continue
        # Allow import-only / comments without SQL SELECT
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line) and "SELECT" in line.upper():
                offenders.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not offenders, (
        "Raw learning_observations SELECT found outside observation_cohort "
        f"(use fetch_* / curriculum_payload_rows):\n" + "\n".join(offenders)
    )


def test_retired_tables_not_hard_required_in_doctor():
    """candidate_observations / signal_forward_labels must not be hard SSOT checks."""
    src = (SRC / "data" / "doctor_checks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # Heuristic: hard=True near retired names in same call is forbidden
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        text = ast.dump(node)
        if "hard" not in text:
            continue
        for retired in _RETIRED_TABLES:
            if retired not in text:
                continue
            # inspect keywords
            for kw in node.keywords:
                if kw.arg == "hard" and isinstance(kw.value, ast.Constant):
                    assert kw.value.value is not True, (
                        f"{retired} must not be hard=True in doctor_checks"
                    )


def test_retired_table_names_not_in_challenge_sql_strings():
    """Challenge product code must not query retired table names."""
    challenge_dir = SRC / "challenge"
    offenders: list[str] = []
    for path in challenge_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for retired in _RETIRED_TABLES:
            if retired in text:
                offenders.append(f"{_rel(path)} mentions {retired}")
    assert not offenders, "\n".join(offenders)


@pytest.mark.live_db
def test_live_db_single_cohort_panel_matches_largest():
    """Optional: ML_SAHAM_DB live path — panel uses largest ACCUM cohort only."""
    db = os.environ.get("ML_SAHAM_DB") or os.path.expanduser(
        "~/dev/ai-saham/data/db/data.db"
    )
    if not Path(db).is_file():
        pytest.skip(f"live DB not found: {db}")

    from ml_saham.data.aisaham_read import connect

    with connect(db) as conn:
        cohorts = list_compatibility_cohorts(
            conn,
            purposes=("ACCUMULATION_DISCOVERY", "ACCUM_PATH", "accum_10d"),
            purpose_like=("%ACCUM%", "%accum%"),
        )
        if len(cohorts) < 1:
            pytest.skip("no ACCUM compatibility cohorts")
        rows, notes, resolved = fetch_accum_observation_raw(conn)
        assert resolved == cohorts[0][0]
        assert len(rows) == cohorts[0][1]
        assert any("compatibility_id" in n for n in notes)
