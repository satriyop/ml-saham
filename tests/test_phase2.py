"""Phase 2: metrics, costs, artifacts, explore flags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.artifacts import (
    SCHEMA_VERSION,
    ArtifactWriteRequest,
    ScoreboardMeta,
    resolve_artifacts_root,
    stub_demo_metrics,
    write_artifact_pack,
)
from ml_saham.cli.app import app
from ml_saham.eval import apply_haircut, bucket_returns, rank_ic, top_quantile_return
from ml_saham.eval.costs import costs_label
from ml_saham.eval.metrics import average_ranks, metrics_bundle

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_progress(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_HOME", str(tmp_path / "home"))


def test_rank_ic_perfect_monotone():
    scores = [1, 2, 3, 4, 5]
    returns = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert abs(rank_ic(scores, returns) - 1.0) < 1e-9


def test_rank_ic_inverse():
    scores = [1, 2, 3, 4, 5]
    returns = [0.5, 0.4, 0.3, 0.2, 0.1]
    assert abs(rank_ic(scores, returns) - (-1.0)) < 1e-9


def test_average_ranks_ties():
    assert average_ranks([10.0, 20.0, 20.0, 30.0]) == [1.0, 2.5, 2.5, 4.0]


def test_bucket_and_top_quantile():
    scores = list(range(10))
    returns = [float(i) for i in range(10)]
    buckets = bucket_returns(scores, returns, n_buckets=5, benchmark_return=4.0)
    assert len(buckets) == 5
    assert buckets[-1].mean_return > buckets[0].mean_return
    top = top_quantile_return(scores, returns, quantile=0.2, benchmark_return=0.0)
    assert top["n"] == 2
    assert top["mean_return"] == 8.5  # 9 and 8


def test_apply_haircut_and_label():
    out = apply_haircut([0.01, 0.02], roundtrip_bps=20.0)
    assert abs(out[0] - (0.01 - 0.002)) < 1e-12
    assert costs_label(with_costs=False) == "gross_banner"
    assert costs_label(with_costs=True) == "simple_haircut"


def test_write_artifact_pack(tmp_path: Path):
    metrics = metrics_bundle([1, 2, 3, 4], [0.1, 0.2, 0.0, 0.3])
    pack = write_artifact_pack(
        ArtifactWriteRequest(
            topic="orientasi",
            chapter=0,
            mode="demo",
            db_path=tmp_path / "x.db",
            model="stub",
            scoreboard=ScoreboardMeta(costs="gross_banner"),
            summary_md="# hello",
            metrics=metrics,
            pack_slug="fixed_demo",
        ),
        artifacts_root=tmp_path / "arts",
    )
    assert pack.manifest_path.is_file()
    manifest = json.loads(pack.manifest_path.read_text())
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["topic"] == "orientasi"
    assert manifest["mode"] == "demo"
    assert "summary.md" in manifest["files"]
    assert "metrics.json" in manifest["files"]
    assert (pack.path / "metrics.json").is_file()


def test_resolve_artifacts_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(tmp_path / "from_env"))
    assert resolve_artifacts_root(None) == (tmp_path / "from_env").resolve()
    cli = tmp_path / "from_cli"
    assert resolve_artifacts_root(cli) == cli.resolve()


def test_demo_writes_artifact(tmp_path: Path):
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    db = build_mvp_fixture(tmp_path / "mvp.db")
    result = runner.invoke(
        app,
        [
            "--db",
            str(db),
            "--artifacts-dir",
            str(tmp_path / "out"),
            "learn",
            "demo",
            "orientasi",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Artifact:" in result.stdout
    packs = list((tmp_path / "out" / "orientasi").glob("*_demo"))
    assert len(packs) == 1
    manifest = json.loads((packs[0] / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert (packs[0] / "metrics.json").is_file()
    metrics = json.loads((packs[0] / "metrics.json").read_text())
    assert metrics.get("mvp_hard_ok") is True


def test_demo_no_artifact(tmp_path: Path):
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    db = build_mvp_fixture(tmp_path / "mvp.db")
    result = runner.invoke(
        app,
        [
            "--db",
            str(db),
            "--artifacts-dir",
            str(tmp_path / "out"),
            "learn",
            "demo",
            "orientasi",
            "--no-artifact",
        ],
    )
    assert result.exit_code == 0
    assert "Artifact:" not in result.stdout
    assert not (tmp_path / "out").exists()


def test_compare_artifacts(tmp_path: Path):
    from tests.fixtures.build_mvp_fixture import build_mvp_fixture

    root = tmp_path / "out"
    db = build_mvp_fixture(tmp_path / "mvp.db")
    cmp = runner.invoke(
        app,
        [
            "--db",
            str(db),
            "--artifacts-dir",
            str(root),
            "learn",
            "compare",
            "factor-score",
            "--baseline",
            "equal-weight",
            "--against",
            "elastic-net",
        ],
    )
    assert cmp.exit_code == 0, cmp.stdout
    packs = list((root / "factor-score").glob("*_compare"))
    assert packs
    assert (packs[0] / "compare.json").is_file()


def test_explore_no_pager_verbose():
    result = runner.invoke(
        app,
        ["learn", "explore", "orientasi", "--no-pager", "--verbose"],
    )
    assert result.exit_code == 0
    assert "Masalah" in result.stdout
    assert "fetched_date" in result.stdout or "Detail" in result.stdout


def test_stub_demo_metrics_with_costs():
    gross = stub_demo_metrics(with_costs=False)
    net = stub_demo_metrics(with_costs=True)
    assert gross["top_quantile"]["mean_return"] > net["top_quantile"]["mean_return"]
