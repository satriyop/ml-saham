"""Accum panels must not mix compatibility_id rulebooks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ml_saham.challenge.panel import (
    list_accum_compatibility_cohorts,
    resolve_accum_compatibility_id,
)
from ml_saham.data.aisaham_read import connect
from ml_saham.data.observation_cohort import fetch_accum_observation_raw


def _make_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE learning_observations (
            observation_id TEXT,
            purpose TEXT,
            compatibility_id TEXT,
            captured_at TEXT,
            decision_payload_json TEXT
        );
        """
    )
    # Large older cohort (3 rows)
    for i, t in enumerate(("BBCA", "BBRI", "TLKM")):
        payload = {
            "ticker": t,
            "session_date": f"2026-07-0{i+1}",
            "features_by_window": {
                "7": {
                    "candidate": {
                        "accum_score_breakdown": {
                            "components": [
                                {"key": "cons", "score_points": 10.0},
                                {"key": "streak", "score_points": 8.0},
                                {"key": "vwap", "score_points": 5.0},
                            ]
                        }
                    }
                }
            },
            "canonical_window": 7,
        }
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?,?,?)",
            (
                f"old-{t}",
                "ACCUMULATION_DISCOVERY",
                "sha256:old_cohort_aaaaaaaa",
                f"2026-07-29T10:00:0{i}",
                json.dumps(payload),
            ),
        )
    # Small newer cohort (1 row)
    payload_new = {
        "ticker": "ASII",
        "session_date": "2026-07-30",
        "features_by_window": {
            "7": {
                "candidate": {
                    "accum_score_breakdown": {
                        "components": [
                            {"key": "cons", "score_points": 9.0},
                            {"key": "streak", "score_points": 7.0},
                            {"key": "vwap", "score_points": 4.0},
                        ]
                    }
                }
            }
        },
        "canonical_window": 7,
    }
    conn.execute(
        "INSERT INTO learning_observations VALUES (?,?,?,?,?)",
        (
            "new-ASII",
            "ACCUMULATION_DISCOVERY",
            "sha256:new_cohort_bbbbbbbb",
            "2026-07-30T19:00:00",
            json.dumps(payload_new),
        ),
    )
    conn.commit()
    conn.close()
    return path


def test_list_cohorts_orders_by_size(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        cohorts = list_accum_compatibility_cohorts(conn)
    assert len(cohorts) == 2
    assert cohorts[0][0] == "sha256:old_cohort_aaaaaaaa"
    assert cohorts[0][1] == 3
    assert cohorts[1][0] == "sha256:new_cohort_bbbbbbbb"
    assert cohorts[1][1] == 1


def test_auto_selects_largest_never_mixes(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        cid, notes = resolve_accum_compatibility_id(conn)
        assert cid == "sha256:old_cohort_aaaaaaaa"
        assert any("auto-selected largest" in n for n in notes)
        assert any("excluded" in n for n in notes)

        rows, notes2, resolved = fetch_accum_observation_raw(conn)
        assert resolved == "sha256:old_cohort_aaaaaaaa"
        assert len(rows) == 3
        # no ASII from small cohort
        tickers = []
        for r in rows:
            p = json.loads(r["decision_payload_json"])
            tickers.append(p["ticker"])
        assert "ASII" not in tickers
        assert set(tickers) == {"BBCA", "BBRI", "TLKM"}


def test_explicit_compatibility_id(tmp_path: Path):
    db = _make_db(tmp_path / "c.db")
    with connect(db) as conn:
        rows, notes, resolved = fetch_accum_observation_raw(
            conn, preferred_compatibility_id="sha256:new_cohort_bbbbbbbb"
        )
        assert resolved == "sha256:new_cohort_bbbbbbbb"
        assert len(rows) == 1
        p = json.loads(rows[0]["decision_payload_json"])
        assert p["ticker"] == "ASII"
        assert any("explicit" in n for n in notes)


def test_legacy_fixture_without_column_loads_all(tmp_path: Path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE learning_observations (
            purpose TEXT, captured_at TEXT, decision_payload_json TEXT
        )
        """
    )
    for t in ("A", "B"):
        conn.execute(
            "INSERT INTO learning_observations VALUES (?,?,?)",
            (
                "ACCUMULATION_DISCOVERY",
                "2024-01-01",
                json.dumps({"ticker": t, "session_date": "2024-01-01"}),
            ),
        )
    conn.commit()
    conn.close()
    with connect(db) as c:
        rows, notes, resolved = fetch_accum_observation_raw(c)
        assert resolved is None
        assert len(rows) == 2
        assert notes == []


# ---------------------------------------------------------------------------
# Production-facing: purpose-family population identity (not a universal stamp)
# ---------------------------------------------------------------------------


def test_require_family_compatibility_id_no_auto_select(tmp_path: Path):
    """Family require: missing/unknown → None; never largest auto-select."""
    from ml_saham.data.aisaham_read import connect
    from ml_saham.data.observation_cohort import (
        ACCUM_PURPOSE_LIKE,
        ACCUM_PURPOSES,
        require_family_compatibility_id,
    )
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "fam.db", min_bars=80)
    with connect(db) as conn:
        cid, notes = require_family_compatibility_id(
            conn,
            purposes=ACCUM_PURPOSES,
            purpose_like=ACCUM_PURPOSE_LIKE,
            preferred=None,
            family="ACCUM",
        )
        assert cid is None
        assert any("requires explicit" in n for n in notes)
        assert not any("auto-selected" in n for n in notes)

        cid, notes = require_family_compatibility_id(
            conn,
            purposes=ACCUM_PURPOSES,
            purpose_like=ACCUM_PURPOSE_LIKE,
            preferred="made-up-id",
            family="ACCUM",
        )
        assert cid is None
        assert any("not found among ACCUM" in n for n in notes)
        assert any("refusing production verdict" in n for n in notes)

        cid, notes = require_family_compatibility_id(
            conn,
            purposes=ACCUM_PURPOSES,
            purpose_like=ACCUM_PURPOSE_LIKE,
            preferred=FIXTURE_COMPATIBILITY_ID,
            family="ACCUM",
        )
        assert cid == FIXTURE_COMPATIBILITY_ID
        assert any("explicit ACCUM" in n for n in notes)


def test_accum_and_factor_block_without_or_with_unknown_cohort(tmp_path: Path):
    """ACCUM snapshot-backed policies require a real ACCUM compatibility_id."""
    from ml_saham.challenge.factor_validity import run_factor_challenge
    from ml_saham.challenge.runner import prepare_accum_panel, run_policy_challenge
    from ml_saham.challenge.types import ChallengeStatus, FactorVerdict
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    db = build_mvp_fixture(tmp_path / "prod_gate.db", min_bars=100)

    for missing in (None, "", "  ", "made-up-id"):
        prep = prepare_accum_panel(
            db,
            "screener.accum.score_weights",
            preferred_compatibility_id=missing,  # type: ignore[arg-type]
        )
        assert prep.blocked == ChallengeStatus.BLOCKED_POLICY
        assert not any("auto-selected largest" in n for n in prep.notes)
        assert prep.selected_compatibility_id is None

        run = run_policy_challenge(
            db, write_artifact=False, compatibility_id=missing  # type: ignore[arg-type]
        )
        assert run.status == ChallengeStatus.BLOCKED_POLICY
        assert run.exit_code() == 2
        assert not any("auto-selected largest" in n for n in run.notes)

        fac = run_factor_challenge(
            db,
            factor="consistency",
            write_artifact=False,
            compatibility_id=missing,  # type: ignore[arg-type]
        )
        assert fac.verdict == FactorVerdict.BLOCKED_POLICY


def test_iev_does_not_stamp_irrelevant_compatibility_id(tmp_path: Path):
    """IEV binds iev snapshot batch identity — made-up observation id is not provenance."""
    from ml_saham.challenge.runner import prepare_accum_panel, run_policy_challenge
    from ml_saham.challenge.types import ChallengeStatus
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    db = build_mvp_fixture(tmp_path / "iev.db", min_bars=100)

    # Without observation compatibility_id: IEV still runnable when panel dense.
    prep = prepare_accum_panel(
        db, "screener.pre_open.iev_rank", preferred_compatibility_id=None
    )
    assert prep.blocked is None or prep.blocked == ChallengeStatus.BLOCKED_DATA
    assert prep.selected_compatibility_id is None
    assert not any("(explicit)" in n and "made-up" in n for n in prep.notes)
    assert any("iev" in n.lower() for n in prep.notes)

    # Made-up observation id must not become false explicit cohort provenance.
    result = run_policy_challenge(
        db,
        "screener.pre_open.iev_rank",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id="made-up-id",
    )
    joined = "\n".join(result.notes)
    assert "compatibility_id=made-up-id (explicit)" not in joined
    assert "not applicable to iev_rank" in joined or "ignored" in joined.lower()
    assert result.observation_compatibility_id == ""
    assert result.production_snapshot_id == ""  # static fixture, not verified snapshot
    # Must not claim verified production-policy identity via fabricated cohort.
    if result.status not in (
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    ):
        assert result.status in {
            ChallengeStatus.WIN,
            ChallengeStatus.LOSE,
            ChallengeStatus.INCONCLUSIVE,
        }


def test_pre_open_requires_real_pre_open_cohort(tmp_path: Path):
    """PRE_OPEN observation policies verify PRE_OPEN family — not invent provenance."""
    from ml_saham.challenge.runner import run_policy_challenge
    from ml_saham.challenge.types import ChallengeStatus
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "po.db", min_bars=100)

    missing = run_policy_challenge(
        db,
        "screener.pre_open.directional_score",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id=None,
    )
    assert missing.status == ChallengeStatus.BLOCKED_POLICY
    assert any("PRE_OPEN" in n and "explicit" in n for n in missing.notes)

    fake = run_policy_challenge(
        db,
        "screener.pre_open.directional_score",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id="made-up-id",
    )
    assert fake.status == ChallengeStatus.BLOCKED_POLICY
    assert any("not found among PRE_OPEN" in n for n in fake.notes)
    assert fake.production_snapshot_id == ""

    ok = run_policy_challenge(
        db,
        "screener.pre_open.directional_score",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert ok.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
    }
    if ok.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert ok.observation_compatibility_id == FIXTURE_COMPATIBILITY_ID
        assert ok.production_snapshot_id == ""  # static fixture, not verified snapshot
        assert any("static pre-open policy fixture" in n for n in ok.notes)
        assert any("explicit PRE_OPEN" in n for n in ok.notes)


def test_mixed_engine_purpose_specific_identity(tmp_path: Path):
    """Screener engine: one id is not universal provenance across ACCUM/IEV/PRE_OPEN."""
    from ml_saham.challenge.engines import run_engine_portfolio
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "eng.db", min_bars=100)

    fake = run_engine_portfolio(
        db, "screener", write_artifact=False, compatibility_id="made-up-id"
    )
    assert fake.resolve_error is None  # per-policy fail-closed, not global gate
    by_pid = {r.policy_id: r for r in fake.rows}
    accum = by_pid["screener.accum.score_weights"]
    iev = by_pid["screener.pre_open.iev_rank"]
    directional = by_pid["screener.pre_open.directional_score"]

    assert accum.status == "BLOCKED_POLICY"
    assert any("not found among ACCUM" in n for n in accum.notes)
    assert accum.observation_compatibility_id == ""

    # IEV may score; must not stamp made-up observation cohort as explicit binding.
    assert "compatibility_id=made-up-id (explicit)" not in "\n".join(iev.notes)
    assert iev.observation_compatibility_id == ""
    assert any(
        "not applicable to iev_rank" in n or "iev" in n.lower() for n in iev.notes
    )

    assert directional.status == "BLOCKED_POLICY"
    assert any("not found among PRE_OPEN" in n for n in directional.notes)

    # Valid fixture id exists in both ACCUM and PRE_OPEN in the MVP fixture.
    good = run_engine_portfolio(
        db,
        "screener",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    by_ok = {r.policy_id: r for r in good.rows}
    assert by_ok["screener.accum.score_weights"].status != "BLOCKED_POLICY" or not any(
        "requires explicit" in n for n in by_ok["screener.accum.score_weights"].notes
    )
    assert by_ok["screener.accum.score_weights"].observation_compatibility_id == (
        FIXTURE_COMPATIBILITY_ID
    )
    # IEV still must not claim the observation cohort as its population id.
    assert by_ok["screener.pre_open.iev_rank"].observation_compatibility_id == ""


def test_production_run_with_explicit_fixture_cohort_binds(tmp_path: Path):
    """Explicit fixture id binds ACCUM verified path; not blocked for missing identity."""
    from ml_saham.challenge.runner import run_policy_challenge
    from ml_saham.challenge.types import ChallengeStatus
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "explicit.db", min_bars=120)
    result = run_policy_challenge(
        db,
        "screener.accum.score_weights",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert not any("requires explicit compatibility_id" in n for n in result.notes)
    assert not any("auto-selected largest" in n for n in result.notes)
    assert result.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
    }
    assert result.observation_compatibility_id == FIXTURE_COMPATIBILITY_ID
    assert any("explicit ACCUM" in n for n in result.notes)
    assert result.production_snapshot_id  # verified snapshot path
