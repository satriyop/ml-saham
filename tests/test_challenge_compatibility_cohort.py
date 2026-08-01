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
    """IEV binds typed batch identity; not observation cohort; not production baseline."""
    from ml_saham.challenge.runner import (
        BASELINE_STATIC_REFERENCE,
        prepare_accum_panel,
        run_policy_challenge,
    )
    from ml_saham.challenge.types import ChallengeStatus
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    db = build_mvp_fixture(tmp_path / "iev.db", min_bars=100)

    prep = prepare_accum_panel(
        db, "screener.pre_open.iev_rank", preferred_compatibility_id=None
    )
    assert prep.blocked is None or prep.blocked == ChallengeStatus.BLOCKED_DATA
    assert prep.selected_compatibility_id is None
    if prep.blocked is None:
        assert prep.population_identity_kind == "iev_batch"
        assert prep.population_identity_id.startswith("sha256:")
        assert (prep.population_identity_detail or {}).get("selection_contract")

    result = run_policy_challenge(
        db,
        "screener.pre_open.iev_rank",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id="made-up-id",
        baseline="static_reference",
    )
    joined = "\n".join(result.notes)
    assert "compatibility_id=made-up-id (explicit)" not in joined
    assert "not applicable to iev_rank" in joined or "ignored" in joined.lower()
    assert result.observation_compatibility_id == ""
    assert result.production_snapshot_id == ""
    assert result.baseline_id == BASELINE_STATIC_REFERENCE
    assert "Baseline: production" not in "\n".join(result.lines)
    assert any("static_reference" in n for n in result.notes)
    if result.status not in (
        ChallengeStatus.BLOCKED_DATA,
        ChallengeStatus.BLOCKED_POLICY,
    ):
        assert result.population_identity_kind == "iev_batch"
        assert result.population_identity_id.startswith("sha256:")
        assert result.population_identity_detail.get("source_table")
        assert result.status in {
            ChallengeStatus.WIN,
            ChallengeStatus.LOSE,
            ChallengeStatus.INCONCLUSIVE,
        }


def test_pre_open_requires_real_pre_open_cohort(tmp_path: Path):
    """PRE_OPEN static fixtures bind PRE_OPEN cohort under static_reference baseline."""
    from ml_saham.challenge.runner import (
        BASELINE_PRODUCTION,
        BASELINE_STATIC_REFERENCE,
        run_policy_challenge,
    )
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
        baseline="static_reference",
    )
    assert missing.status == ChallengeStatus.BLOCKED_POLICY
    assert any("PRE_OPEN" in n and "explicit" in n for n in missing.notes)

    fake = run_policy_challenge(
        db,
        "screener.pre_open.directional_score",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id="made-up-id",
        baseline="static_reference",
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
        baseline="static_reference",
    )
    assert ok.status in {
        ChallengeStatus.WIN,
        ChallengeStatus.LOSE,
        ChallengeStatus.INCONCLUSIVE,
        ChallengeStatus.BLOCKED_DATA,
    }
    if ok.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert ok.observation_compatibility_id == FIXTURE_COMPATIBILITY_ID
        assert ok.production_snapshot_id == ""
        assert ok.baseline_id == BASELINE_STATIC_REFERENCE
        assert ok.baseline_id != BASELINE_PRODUCTION
        assert ok.population_identity_kind == "pre_open_compat"
        assert ok.population_identity_id == FIXTURE_COMPATIBILITY_ID
        assert any("static pre-open policy fixture" in n for n in ok.notes)
        assert any("explicit PRE_OPEN" in n for n in ok.notes)
        assert "Baseline: production" not in "\n".join(ok.lines)
        assert not ok.has_verified_production_identity()


def test_production_baseline_blocked_without_verified_identity(tmp_path: Path):
    """Requested baseline=production without verified snapshot → BLOCKED_POLICY."""
    from ml_saham.challenge.runner import run_policy_challenge
    from ml_saham.challenge.types import ChallengeStatus
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "prod_block.db", min_bars=100)
    blocked = run_policy_challenge(
        db,
        "screener.pre_open.iev_rank",
        against="equal_sleeves",
        write_artifact=False,
        baseline="production",
    )
    assert blocked.status == ChallengeStatus.BLOCKED_POLICY
    assert blocked.baseline_id == "production"
    assert blocked.exit_code() == 2
    assert any("baseline=production requires" in n for n in blocked.notes)
    assert "Baseline: static_reference" not in "\n".join(blocked.lines)

    # Explicit static_reference is the only way to dig static fixtures.
    ok = run_policy_challenge(
        db,
        "screener.pre_open.iev_rank",
        against="equal_sleeves",
        write_artifact=False,
        baseline="static_reference",
    )
    if ok.status not in (ChallengeStatus.BLOCKED_DATA, ChallengeStatus.BLOCKED_POLICY):
        assert ok.baseline_id == "static_reference"


def test_mixed_engine_purpose_specific_identity(tmp_path: Path):
    """Screener engine: purpose-family + baseline honesty per policy."""
    from ml_saham.challenge.engines import run_engine_portfolio
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "eng.db", min_bars=100)

    # Default baseline=production: static pre-open/IEV fail closed (no remap).
    prod = run_engine_portfolio(
        db,
        "screener",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        baseline="production",
    )
    by_prod = {r.policy_id: r for r in prod.rows}
    assert by_prod["screener.accum.score_weights"].status != "ERROR"
    assert by_prod["screener.accum.score_weights"].baseline_id == "production"
    assert by_prod["screener.pre_open.iev_rank"].status == "BLOCKED_POLICY"
    assert any(
        "baseline=production requires" in n
        for n in by_prod["screener.pre_open.iev_rank"].notes
    )
    assert by_prod["screener.pre_open.directional_score"].status == "BLOCKED_POLICY"

    # Explicit static_reference digs: IEV/PRE_OPEN can run; ACCUM also allowed as ref dig.
    ref = run_engine_portfolio(
        db,
        "screener",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        baseline="static_reference",
    )
    by_ref = {r.policy_id: r for r in ref.rows}
    iev = by_ref["screener.pre_open.iev_rank"]
    assert iev.observation_compatibility_id == ""
    assert iev.baseline_id == "static_reference"
    if iev.status not in ("BLOCKED_DATA", "BLOCKED_POLICY"):
        assert iev.population_identity_kind == "iev_batch"
        assert iev.population_identity_id.startswith("sha256:")

    fake = run_engine_portfolio(
        db,
        "screener",
        write_artifact=False,
        compatibility_id="made-up-id",
        baseline="static_reference",
    )
    by_fake = {r.policy_id: r for r in fake.rows}
    assert by_fake["screener.accum.score_weights"].status == "BLOCKED_POLICY"
    assert by_fake["screener.pre_open.directional_score"].status == "BLOCKED_POLICY"
    assert "compatibility_id=made-up-id (explicit)" not in "\n".join(
        by_fake["screener.pre_open.iev_rank"].notes
    )


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
    assert result.baseline_id == "production"
    assert result.has_verified_production_identity()
    assert result.population_identity_kind == "accum_compat"
    assert result.population_identity_id == FIXTURE_COMPATIBILITY_ID


def test_static_reference_not_promote_eligible(tmp_path: Path):
    """baseline=static_reference is refused for verified production promote packets."""
    import json

    from ml_saham.challenge.promote import build_promote_packet
    from ml_saham.challenge.runner import run_policy_challenge
    from tests.fixtures.build_mvp_fixture import (
        FIXTURE_COMPATIBILITY_ID,
        build_mvp_fixture,
    )

    db = build_mvp_fixture(tmp_path / "prom.db", min_bars=100)
    result = run_policy_challenge(
        db,
        "screener.accum.score_weights",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert result.has_verified_production_identity()
    export = tmp_path / "ref.json"
    export.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "status": result.status.value,
                "policy_id": result.policy_id,
                "protocol_id": result.protocol_id,
                "baseline_id": "static_reference",
                "against_id": result.against_id,
                "observation_compatibility_id": result.observation_compatibility_id,
                "production_snapshot_id": result.production_snapshot_id,
                "production_snapshot_digest": result.production_snapshot_digest,
                "production_policy_id": result.production_policy_id,
                "production_policy_version": result.production_policy_version,
                "production_semantic_engine_contract_id": (
                    result.production_semantic_engine_contract_id
                ),
                "challenge_adapter_id": result.challenge_adapter_id,
                "challenge_adapter_version": result.challenge_adapter_version,
            }
        ),
        encoding="utf-8",
    )
    pack = build_promote_packet(from_json=export, write_artifact=False)
    assert pack.exit_code() == 2
    assert pack.error
    assert "static_reference" in pack.error
    assert "not eligible" in pack.error
