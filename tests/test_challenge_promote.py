"""Promote packet from challenge exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.artifacts import (
    CHALLENGE_ARTIFACT_SCHEMA_VERSION,
    challenge_result_export_payload,
)
from ml_saham.challenge.promote import (
    build_promote_packet,
    load_evidence_artifact,
    validate_artifact_schema_version,
    validate_production_identity_format,
    validate_verified_production_identity,
)
from ml_saham.challenge.production_policy_snapshots import stable_snapshot_id_for
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.cli.app import app
from ml_saham.data.aisaham_read import connect as aisaham_connect
from tests.fixtures.build_mvp_fixture import FIXTURE_COMPATIBILITY_ID, build_mvp_fixture

runner = CliRunner()


def _export_from_result(result) -> dict:
    """Promote-eligible export: always stamps exact integer schema_version."""
    return challenge_result_export_payload(result)


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "prom.db", min_bars=120)


@pytest.fixture
def verified_export(fixture_db: Path) -> dict:
    """Authentic identities from the real challenge path (not hand-fabricated)."""
    result = run_policy_challenge(
        fixture_db,
        "screener.accum.score_weights",
        against="equal_sleeves",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    assert result.production_snapshot_id, result.notes
    assert result.observation_compatibility_id == FIXTURE_COMPATIBILITY_ID
    return _export_from_result(result)


def test_promote_from_champion_export(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        "screener.accum.score_weights",
        against="lgbm_reweight",
        write_artifact=False,
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
    )
    # Champion may BLOCKED on missing lightgbm, but prep still stamps verified identity.
    assert result.production_snapshot_id, result.notes
    export = tmp_path / "champ.json"
    payload = {
        "mode": "champion",
        **_export_from_result(result),
        "against_id": "lgbm_reweight",
    }
    export.write_text(json.dumps(payload), encoding="utf-8")

    pack = build_promote_packet(
        from_json=export,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        db_path=fixture_db,
    )
    assert pack.exit_code() == 0, pack.error
    assert pack.error is None
    assert pack.policy_id == "screener.accum.score_weights"
    assert pack.mode == "champion"
    assert pack.artifact_dir is not None
    promote_md = (pack.artifact_dir / "PROMOTE.md").read_text(encoding="utf-8")
    assert "NOT applied" in promote_md or "NOT APPLIED" in promote_md.upper()
    assert "never writes" in promote_md.lower() or "never" in promote_md.lower()
    assert "screener.accum.score_weights" in promote_md
    assert "lgbm_reweight" in promote_md
    assert (pack.artifact_dir / "evidence.json").is_file()
    assert pack.evidence.get("production_snapshot_id") == result.production_snapshot_id


def test_promote_from_verified_tune_export(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Real challenge export with verified identities → human-only promote packet."""
    export = tmp_path / "tune.json"
    export.write_text(json.dumps(verified_export), encoding="utf-8")
    pack = build_promote_packet(
        from_json=export,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
        db_path=fixture_db,
    )
    assert pack.exit_code() == 0, pack.error
    assert pack.error is None
    assert pack.policy_id == verified_export["policy_id"]
    assert (
        pack.evidence["production_snapshot_id"]
        == verified_export["production_snapshot_id"]
    )
    assert pack.evidence["observation_compatibility_id"] == FIXTURE_COMPATIBILITY_ID
    md = pack.summary_md
    assert "NOT applied" in md
    assert "never" in md.lower()
    # recomputed identity matches export (shipped rules)
    expected = stable_snapshot_id_for(
        compatibility_id=FIXTURE_COMPATIBILITY_ID,
        policy_id="screener.accum.score_weights",
    )
    assert pack.evidence["production_snapshot_id"] == expected


def test_promote_bad_json(tmp_path: Path, fixture_db: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"foo": 1}\n', encoding="utf-8")
    pack = build_promote_packet(from_json=bad, write_artifact=False, db_path=fixture_db)
    assert pack.exit_code() == 2
    assert pack.error


def test_legacy_export_is_not_promotion_eligible(tmp_path: Path, fixture_db: Path):
    # Pre-identity export (even with schema) cannot create a verified promote packet.
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "schema_version": CHALLENGE_ARTIFACT_SCHEMA_VERSION,
                "status": "WIN",
                "policy_id": "screener.accum.score_weights",
                "protocol_id": "accum_path_v1",
                "baseline_id": "production",
                "against_id": "equal_sleeves",
            }
        ),
        encoding="utf-8",
    )
    pack = build_promote_packet(
        from_json=legacy, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "historical artifact" in (pack.error or "")
    assert "missing" in (pack.error or "")


def test_export_without_schema_version_rejected(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Bare challenge export missing schema_version is not promote-eligible."""
    payload = dict(verified_export)
    del payload["schema_version"]
    path = tmp_path / "no_schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "schema_version" in (pack.error or "")
    assert "missing" in (pack.error or "")


def test_schema_version_must_be_exact_integer(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """No int(...) coercion: strings, floats, and bools are rejected."""
    for bad in ("2", 2.0, True, False):
        payload = dict(verified_export)
        payload["schema_version"] = bad
        path = tmp_path / f"schema_bad_{type(bad).__name__}.json"
        # json.dumps turns True→true; write via dumps for realistic wire form where possible
        path.write_text(json.dumps(payload), encoding="utf-8")
        pack = build_promote_packet(
            from_json=path, write_artifact=False, db_path=fixture_db
        )
        assert pack.exit_code() == 2, (bad, pack.error)
        err = pack.error or ""
        assert "schema_version" in err, (bad, err)

    # Exact integer CHALLENGE_ARTIFACT_SCHEMA_VERSION is the accepted contract.
    assert verified_export["schema_version"] == CHALLENGE_ARTIFACT_SCHEMA_VERSION
    assert type(verified_export["schema_version"]) is int
    assert validate_artifact_schema_version(verified_export) is None


def test_fabricated_snapshot_id_rejected(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Non-empty placeholder snapshot id is not a verified production identity."""
    payload = dict(verified_export)
    payload["production_snapshot_id"] = "x"
    path = tmp_path / "fab.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert pack.error
    assert "production identity invalid" in pack.error
    assert "production_snapshot_id format" in pack.error
    assert "historical artifact" not in pack.error  # validity, not mere presence
    assert pack.summary_md == "" or "PROMOTE PACKET" not in "\n".join(pack.lines)


def test_fabricated_digest_and_compat_rejected(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    for field, value, needle in (
        (
            "production_snapshot_digest",
            "not-a-digest",
            "production_snapshot_digest format",
        ),
        ("observation_compatibility_id", "x", "observation_compatibility_id format"),
        (
            "production_snapshot_digest",
            "sha256:" + "ab" * 32,  # prefixed form is not the payload digest shape
            "production_snapshot_digest format",
        ),
    ):
        payload = dict(verified_export)
        payload[field] = value
        # Keep snapshot id recomputable only when we are not testing snap format;
        # wrong compat will also fail recompute if format passes — use short compat.
        path = tmp_path / f"bad_{field}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        pack = build_promote_packet(
            from_json=path, write_artifact=False, db_path=fixture_db
        )
        assert pack.exit_code() == 2, (field, pack.error)
        assert needle in (pack.error or ""), (field, pack.error)


def test_policy_id_mismatch_and_wrong_snapshot_recompute(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    payload = dict(verified_export)
    payload["production_policy_id"] = "signal.accum.raw_score"
    path = tmp_path / "mismatch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "does not equal policy_id" in (pack.error or "")

    # Same policy ids but snapshot_id not derived from this cohort+policy
    payload = dict(verified_export)
    payload["production_snapshot_id"] = "ab" * 32  # valid hex format, wrong identity
    path2 = tmp_path / "recompute.json"
    path2.write_text(json.dumps(payload), encoding="utf-8")
    pack2 = build_promote_packet(
        from_json=path2, write_artifact=False, db_path=fixture_db
    )
    assert pack2.exit_code() == 2
    assert "recomputed" in (pack2.error or "") or "identity mismatch" in (
        pack2.error or ""
    )


def test_unsupported_adapter_protocol_and_schema(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    payload = dict(verified_export)
    payload["challenge_adapter_id"] = "fabricated.adapter"
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "challenge_adapter_id" in (pack.error or "")

    payload = dict(verified_export)
    payload["protocol_id"] = "not_a_real_protocol_v9"
    path = tmp_path / "proto.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    err = pack.error or ""
    assert "protocol" in err.lower()

    # Unsupported integer schema_version fails closed
    payload = dict(verified_export)
    payload["schema_version"] = 99
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "schema_version" in (pack.error or "")
    assert "unsupported" in (pack.error or "")


def test_artifact_dir_requires_schema_and_valid_identity(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Manifest-shaped artifact packs require schema_version + valid identities."""
    art = tmp_path / "artifact_bad"
    art.mkdir()
    # Missing schema_version on manifest
    (art / "manifest.json").write_text(
        json.dumps(
            {
                "policy_id": verified_export["policy_id"],
                "protocol_id": verified_export["protocol_id"],
                "baseline_id": "production",
                "against_id": "equal_sleeves",
                "status": verified_export["status"],
                **{
                    k: verified_export[k]
                    for k in (
                        "observation_compatibility_id",
                        "production_snapshot_id",
                        "production_snapshot_digest",
                        "production_policy_id",
                        "production_policy_version",
                        "production_semantic_engine_contract_id",
                        "challenge_adapter_id",
                        "challenge_adapter_version",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    (art / "metrics.json").write_text(
        json.dumps({"status": verified_export["status"]}), encoding="utf-8"
    )
    with aisaham_connect(fixture_db) as conn:
        data, err = load_evidence_artifact(art, conn=conn)
    assert data is None
    assert err is not None
    assert "schema_version" in err

    # Valid manifest-shaped artifact
    art_ok = tmp_path / "artifact_ok"
    art_ok.mkdir()
    (art_ok / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": CHALLENGE_ARTIFACT_SCHEMA_VERSION,
                "mode": "challenge_run",
                "policy_id": verified_export["policy_id"],
                "protocol_id": verified_export["protocol_id"],
                "baseline_id": "production",
                "against_id": "equal_sleeves",
                "status": verified_export["status"],
                "n_rows": verified_export["n_rows"],
                "primary_horizon": verified_export["primary_horizon"],
                **{
                    k: verified_export[k]
                    for k in (
                        "observation_compatibility_id",
                        "production_snapshot_id",
                        "production_snapshot_digest",
                        "production_policy_id",
                        "production_policy_version",
                        "production_semantic_engine_contract_id",
                        "challenge_adapter_id",
                        "challenge_adapter_version",
                        "population_identity_kind",
                        "population_identity_id",
                        "population_identity_detail",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    (art_ok / "metrics.json").write_text(
        json.dumps(
            {
                "status": verified_export["status"],
                "primary_ic_baseline": verified_export.get("primary_ic_baseline"),
                "primary_ic_against": verified_export.get("primary_ic_against"),
            }
        ),
        encoding="utf-8",
    )
    pack = build_promote_packet(
        from_artifact=art_ok, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 0, pack.error
    assert (
        pack.evidence["production_snapshot_id"]
        == verified_export["production_snapshot_id"]
    )
    assert pack.evidence["schema_version"] == CHALLENGE_ARTIFACT_SCHEMA_VERSION


def test_export_json_cannot_bypass_manifest_schema(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """When manifest.json exists, export.json must not skip manifest validation."""
    art = tmp_path / "mixed"
    art.mkdir()
    # Manifest is missing schema_version → must fail even if export.json is rich.
    (art / "manifest.json").write_text(
        json.dumps(
            {
                "policy_id": verified_export["policy_id"],
                "protocol_id": verified_export["protocol_id"],
                "baseline_id": "production",
                "against_id": "equal_sleeves",
                "status": verified_export["status"],
                **{
                    k: verified_export[k]
                    for k in (
                        "observation_compatibility_id",
                        "production_snapshot_id",
                        "production_snapshot_digest",
                        "production_policy_id",
                        "production_policy_version",
                        "production_semantic_engine_contract_id",
                        "challenge_adapter_id",
                        "challenge_adapter_version",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    (art / "metrics.json").write_text(
        json.dumps({"status": verified_export["status"]}), encoding="utf-8"
    )
    # Fully valid standalone export would succeed alone — must not rescue bad manifest.
    (art / "export.json").write_text(json.dumps(verified_export), encoding="utf-8")
    with aisaham_connect(fixture_db) as conn:
        data, err = load_evidence_artifact(art, conn=conn)
    assert data is None
    assert err is not None
    assert "schema_version" in err

    # Standalone export.json (no manifest) with schema works.
    solo = tmp_path / "solo_export"
    solo.mkdir()
    (solo / "export.json").write_text(json.dumps(verified_export), encoding="utf-8")
    pack = build_promote_packet(
        from_artifact=solo, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 0, pack.error
    assert pack.evidence["schema_version"] == CHALLENGE_ARTIFACT_SCHEMA_VERSION

    # Standalone export.json without schema fails closed.
    solo_bad = tmp_path / "solo_export_bad"
    solo_bad.mkdir()
    bare = dict(verified_export)
    del bare["schema_version"]
    (solo_bad / "export.json").write_text(json.dumps(bare), encoding="utf-8")
    pack_bad = build_promote_packet(
        from_artifact=solo_bad, write_artifact=False, db_path=fixture_db
    )
    assert pack_bad.exit_code() == 2
    assert "schema_version" in (pack_bad.error or "")


def test_validate_presence_only_placeholders_rejected():
    """Pure unit: truthy placeholders fail validity (not only missing-field path)."""
    fake = {
        "schema_version": CHALLENGE_ARTIFACT_SCHEMA_VERSION,
        "status": "WIN",
        "policy_id": "screener.accum.score_weights",
        "protocol_id": "accum_path_v1",
        "baseline_id": "production",
        "against_id": "equal_sleeves",
        "observation_compatibility_id": "x",
        "production_snapshot_id": "x",
        "production_snapshot_digest": "x",
        "production_policy_id": "x",
        "production_policy_version": "x",
        "production_semantic_engine_contract_id": "x",
        "challenge_adapter_id": "x",
        "challenge_adapter_version": "x",
        "population_identity_kind": "accum_compat",
        "population_identity_id": "x",
        "population_identity_detail": {"kind": "accum_compat", "compatibility_id": "x"},
    }
    err = validate_production_identity_format(fake)
    assert err is not None
    assert "production identity invalid" in err or "format" in err

    # "Verified" API always requires a live DB connection (no format-only default).
    import inspect

    sig = inspect.signature(validate_verified_production_identity)
    assert "conn" in sig.parameters
    assert sig.parameters["conn"].default is inspect.Parameter.empty


def test_v3_population_identity_required_for_promote(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Omitting population_identity_* from an otherwise valid v3 export fails closed."""
    for field in (
        "population_identity_kind",
        "population_identity_id",
        "population_identity_detail",
    ):
        payload = dict(verified_export)
        del payload[field]
        path = tmp_path / f"no_{field}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        pack = build_promote_packet(
            from_json=path, write_artifact=False, db_path=fixture_db
        )
        assert pack.exit_code() == 2, (field, pack.error)
        assert "population identity" in (pack.error or "").lower() or field in (
            pack.error or ""
        )

    # Wrong kind
    payload = dict(verified_export)
    payload["population_identity_kind"] = "iev_batch"
    path = tmp_path / "wrong_kind.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "accum_compat" in (pack.error or "")

    # id must match observation_compatibility_id
    payload = dict(verified_export)
    payload["population_identity_id"] = "sha256:other_cohort_not_matching"
    path = tmp_path / "wrong_pop_id.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert "population_identity_id" in (pack.error or "")


def test_promote_cli(fixture_db: Path, tmp_path: Path, verified_export: dict):
    export = tmp_path / "run.json"
    export.write_text(json.dumps(verified_export), encoding="utf-8")
    r = runner.invoke(
        app,
        [
            "--db",
            str(fixture_db),
            "--artifacts-dir",
            str(tmp_path / "a"),
            "challenge",
            "promote-packet",
            "--from-json",
            str(export),
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "PROMOTE" in r.stdout or "Promote" in r.stdout
    assert "NOT APPLIED" in r.stdout.upper() or "not applied" in r.stdout.lower()


def test_promote_cli_rejects_fabricated(tmp_path: Path, verified_export: dict):
    payload = dict(verified_export)
    payload["production_snapshot_id"] = "x"
    export = tmp_path / "bad.json"
    export.write_text(json.dumps(payload), encoding="utf-8")
    r = runner.invoke(
        app,
        [
            "challenge",
            "promote-packet",
            "--from-json",
            str(export),
            "--no-artifact",
        ],
    )
    assert r.exit_code == 2
    out = (r.stdout or "") + (r.stderr or "")
    assert "BLOCKED" in out or "invalid" in out.lower()


def test_fabricated_zero_digest_rejected_against_db(
    verified_export: dict, tmp_path: Path, fixture_db: Path
):
    """Valid hex format alone must not pass without authoritative DB match."""
    payload = dict(verified_export)
    payload["production_snapshot_digest"] = "0" * 64
    # Keep recomputed snapshot_id consistent so only digest authenticity fails.
    path = tmp_path / "zero_digest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    pack = build_promote_packet(
        from_json=path, write_artifact=False, db_path=fixture_db
    )
    assert pack.exit_code() == 2
    assert pack.error
    assert "production_snapshot_digest" in pack.error or "payload_digest" in pack.error
    assert "authoritative" in pack.error or "does not match" in pack.error
