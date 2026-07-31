"""Promote packet from challenge exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.promote import build_promote_packet
from ml_saham.challenge.runner import run_policy_challenge
from ml_saham.cli.app import app
from tests.fixtures.build_mvp_fixture import build_mvp_fixture

runner = CliRunner()


def _identity(result) -> dict[str, str]:
    return {
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


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    return build_mvp_fixture(tmp_path / "prom.db", min_bars=120)


def test_promote_from_champion_export(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        "screener.accum.score_weights",
        against="lgbm_reweight",
        write_artifact=False,
    )
    export = tmp_path / "champ.json"
    payload = {
        "mode": "champion",
        "status": result.status.value,
        "policy_id": result.policy_id,
        "protocol_id": result.protocol_id,
        "policy_hash": result.policy_hash,
        "baseline_id": result.baseline_id,
        "against_id": result.against_id,
        "n_rows": result.n_rows,
        "primary_horizon": result.primary_horizon,
        "primary_ic_baseline": result.primary_ic_baseline,
        "primary_ic_against": result.primary_ic_against,
        "weights": result.weights,
        "notes": result.notes,
        "fold_metrics": result.fold_metrics,
        **_identity(result),
    }
    export.write_text(json.dumps(payload), encoding="utf-8")

    pack = build_promote_packet(
        from_json=export,
        write_artifact=True,
        artifacts_dir=tmp_path / "arts",
    )
    assert pack.exit_code() == 0
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


def test_promote_bad_json(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"foo": 1}\n', encoding="utf-8")
    pack = build_promote_packet(from_json=bad, write_artifact=False)
    assert pack.exit_code() == 2
    assert pack.error


def test_legacy_export_is_not_promotion_eligible(tmp_path: Path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "status": "WIN",
                "policy_id": "screener.accum.score_weights",
                "protocol_id": "accum_path_v1",
                "baseline_id": "production",
                "against_id": "equal_sleeves",
            }
        ),
        encoding="utf-8",
    )
    pack = build_promote_packet(from_json=legacy, write_artifact=False)
    assert pack.exit_code() == 2
    assert "historical artifact" in (pack.error or "")


def test_promote_cli(fixture_db: Path, tmp_path: Path):
    result = run_policy_challenge(
        fixture_db,
        against="equal_sleeves",
        write_artifact=False,
    )
    export = tmp_path / "run.json"
    export.write_text(
        json.dumps(
            {
                "status": result.status.value,
                "policy_id": result.policy_id,
                "protocol_id": result.protocol_id,
                "policy_hash": result.policy_hash,
                "baseline_id": "production",
                "against_id": "equal_sleeves",
                "primary_ic_baseline": result.primary_ic_baseline,
                "primary_ic_against": result.primary_ic_against,
                "n_rows": result.n_rows,
                "notes": result.notes,
                **_identity(result),
            }
        ),
        encoding="utf-8",
    )
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
