"""Phase 3: validated artifact history, compare, promote handoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml_saham.challenge.workbench import build_challenge_workbench


def _write_pack(
    root: Path,
    name: str,
    *,
    schema_version: int,
    status: str = "INCONCLUSIVE",
    policy_id: str = "screener.accum.score_weights",
    protocol_id: str = "accum_path_v1",
    baseline_id: str | None = "production",
    against_id: str = "equal_sleeves",
    primary_horizon: int = 10,
    compat: str = "sha256:aaaa1111bbbb2222",
    population_kind: str = "accum_compat",
    population_id: str = "sha256:aaaa1111bbbb2222",
    ic_against: float = 0.10,
    sealed: bool = False,
) -> Path:
    pack = root / "challenge" / policy_id / name
    pack.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "schema_version": schema_version,
        "mode": "challenge_run",
        "track": "policy_tournament",
        "policy_id": policy_id,
        "protocol_id": protocol_id,
        "status": status,
        "against_id": against_id,
        "primary_horizon": primary_horizon,
        "n_rows": 100,
        "observation_compatibility_id": compat,
        "population_identity_kind": population_kind,
        "population_identity_id": population_id,
        "created_at": "2026-08-02T12:00:00+07:00",
    }
    if baseline_id is not None:
        manifest["baseline_id"] = baseline_id
    if schema_version >= 4:
        manifest["production_snapshot_id"] = "a" * 64
        manifest["production_snapshot_digest"] = "b" * 64
        manifest["production_policy_id"] = policy_id
        manifest["production_policy_version"] = "v1"
        manifest["production_semantic_engine_contract_id"] = "accum_score_policy.v1"
        manifest["challenge_adapter_id"] = "ml-saham.adapter"
        manifest["challenge_adapter_version"] = "v1"
    metrics = {
        "status": status,
        "primary_ic_baseline": 0.12,
        "primary_ic_against": ic_against,
        "horizon_metrics": {"baseline": {"10": 0.12}, "against": {"10": ic_against}},
        "fold_metrics": [
            {
                "fold": 0,
                "ic_baseline": 0.12,
                "ic_against": ic_against,
                "n_test": 20,
            }
        ],
    }
    (pack / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (pack / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    (pack / "summary.md").write_text(f"# {status}\n", encoding="utf-8")
    if sealed:
        (pack / "weights.json").write_text("{}\n", encoding="utf-8")
        (pack / "pack_binding.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "artifact_id": "x" * 16,
                    "content_digest": "c" * 64,
                    "members": ["manifest.json", "metrics.json", "weights.json"],
                    "file_digests": {
                        "manifest.json": "d" * 64,
                        "metrics.json": "e" * 64,
                        "weights.json": "f" * 64,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return pack


def test_list_and_open_historical_display_only(tmp_path: Path):
    art = tmp_path / "artifacts"
    pack = _write_pack(art, "hist1", schema_version=2, baseline_id="production")
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    items = service.list_challenge_artifacts()
    assert len(items) == 1
    assert items[0].openable is True
    assert items[0].promotion_eligible_hint is False
    assert "historical" in (items[0].promotion_block_reason or "").lower()

    opened = service.open_challenge_artifact(pack)
    assert opened.ok is True
    assert opened.historical_display_only is True
    assert opened.promotion_eligible is False
    assert opened.status == "INCONCLUSIVE"
    assert opened.primary_ic_against == pytest.approx(0.10)
    names = {f.name for f in opened.files}
    assert "manifest.json" in names
    assert "metrics.json" in names
    assert "summary.md" in names


def test_open_missing_baseline_not_promotion_eligible(tmp_path: Path):
    art = tmp_path / "artifacts"
    pack = _write_pack(
        art, "nobase", schema_version=4, baseline_id=None, sealed=True
    )
    # remove baseline after write for v4 shape without baseline
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("baseline_id", None)
    (pack / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    opened = service.open_challenge_artifact(pack)
    assert opened.ok is True
    assert opened.promotion_eligible is False
    assert "baseline" in (opened.promotion_block_reason or "").lower()


def test_compare_compatible_has_delta_incompatible_no_winner(tmp_path: Path):
    art = tmp_path / "artifacts"
    left = _write_pack(art, "L", schema_version=2, ic_against=0.10, status="LOSE")
    right = _write_pack(art, "R", schema_version=2, ic_against=0.20, status="WIN")
    other = _write_pack(
        art,
        "O",
        schema_version=2,
        protocol_id="pre_open_session_v1",
        primary_horizon=0,
        ic_against=0.50,
    )
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    ok = service.compare_challenge_artifacts(left, right)
    assert ok.compatible is True
    assert ok.delta_ic_against == pytest.approx(0.10)
    assert ok.winner_banner is not None

    bad = service.compare_challenge_artifacts(left, other)
    assert bad.compatible is False
    assert bad.delta_ic_against is None
    assert bad.winner_banner is None
    assert any(not a.compatible for a in bad.axes)


def test_download_bytes_exact(tmp_path: Path):
    art = tmp_path / "artifacts"
    pack = _write_pack(art, "dl", schema_version=2)
    expected = (pack / "summary.md").read_bytes()
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    data, err = service.read_artifact_file_bytes(pack, "summary.md")
    assert err is None
    assert data == expected
    bad, err2 = service.read_artifact_file_bytes(pack, "../secrets.txt")
    assert bad is None
    assert err2 is not None


def test_promote_packet_fails_closed_on_historical(tmp_path: Path):
    art = tmp_path / "artifacts"
    pack = _write_pack(art, "promo", schema_version=2)
    service = build_challenge_workbench(
        db_path=tmp_path / "missing.db",
        artifacts_root=art,
    )
    packet = service.create_promote_packet(pack, write_artifact=False)
    assert packet.ok is False
    assert packet.auto_applied is False
    assert packet.error


def test_streamlit_history_page_loads(monkeypatch, tmp_path: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    art = tmp_path / "artifacts"
    _write_pack(art, "ui1", schema_version=2)
    monkeypatch.setenv("ML_SAHAM_DB", str(tmp_path / "missing.db"))
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(art))
    app_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ml_saham"
        / "ui"
        / "streamlit_app.py"
    )
    rendered = AppTest.from_file(str(app_path), default_timeout=15).run()
    assert not rendered.exception
