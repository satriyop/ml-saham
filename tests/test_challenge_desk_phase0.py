"""Phase 0 contract tests for the optional local Challenge Desk."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ml_saham.challenge.workbench import build_challenge_workbench
from ml_saham.cli.app import app
from ml_saham.ui import launcher


ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def _request(tmp_path: Path, **overrides) -> launcher.ChallengeDeskLaunchRequest:
    values = {
        "db_path": tmp_path / "upstream.db",
        "artifacts_root": tmp_path / "artifacts",
        "host": "127.0.0.1",
        "port": 8501,
        "no_browser": False,
    }
    values.update(overrides)
    return launcher.ChallengeDeskLaunchRequest(**values)


def test_workbench_overview_is_immutable_and_does_not_touch_paths(tmp_path: Path):
    db_path = tmp_path / "missing" / "upstream.db"
    artifacts_root = tmp_path / "missing" / "artifacts"

    service = build_challenge_workbench(
        db_path=db_path,
        artifacts_root=artifacts_root,
    )
    overview = service.describe()

    assert overview.upstream_db_path == db_path.resolve()
    assert overview.artifacts_root == artifacts_root.resolve()
    assert overview.upstream_access_mode == "read-only"
    assert "automatic promotion is disabled" in overview.production_changes
    assert not db_path.exists()
    assert not artifacts_root.exists()
    with pytest.raises(FrozenInstanceError):
        overview.product_name = "mutated"  # type: ignore[misc]


def test_core_cli_import_does_not_import_or_require_streamlit():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import ml_saham.cli.app; "
                "assert 'streamlit' not in sys.modules"
            ),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_launcher_uses_official_module_command_and_explicit_environment(tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_run(command, *, env, check):
        captured.update(command=command, env=env, check=check)
        return subprocess.CompletedProcess(command, 7)

    request = _request(
        tmp_path,
        host="localhost",
        port=8123,
        no_browser=True,
    )
    exit_code = launcher.launch_challenge_desk(
        request,
        find_spec=lambda name: object(),
        run_process=fake_run,
    )

    command = captured["command"]
    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert "--server.address" in command
    assert command[command.index("--server.address") + 1] == "localhost"
    assert command[command.index("--server.port") + 1] == "8123"
    assert command[command.index("--server.headless") + 1] == "true"
    assert captured["check"] is False
    child_env = captured["env"]
    assert child_env["ML_SAHAM_DB"] == str(request.db_path)
    assert child_env["ML_SAHAM_ARTIFACTS"] == str(request.artifacts_root)
    assert exit_code == 7


def test_launcher_missing_extra_has_exact_install_hint(tmp_path: Path):
    with pytest.raises(launcher.ChallengeDeskDependencyError) as exc_info:
        launcher.launch_challenge_desk(
            _request(tmp_path),
            find_spec=lambda name: None,
        )
    assert launcher.UI_INSTALL_HINT in str(exc_info.value)


@pytest.mark.parametrize("host", ["0.0.0.0", "example.com", "192.168.1.10", ""])
def test_launcher_rejects_non_loopback_hosts(tmp_path: Path, host: str):
    with pytest.raises(launcher.ChallengeDeskLaunchError, match="local-only"):
        launcher.build_streamlit_command(_request(tmp_path, host=host))


@pytest.mark.parametrize("port", [0, 65536])
def test_launcher_rejects_invalid_ports(tmp_path: Path, port: int):
    with pytest.raises(launcher.ChallengeDeskLaunchError, match="port"):
        launcher.build_streamlit_command(_request(tmp_path, port=port))


def test_cli_desk_maps_global_paths_and_launcher_options(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_launch(request):
        captured["request"] = request
        return 0

    monkeypatch.setattr(launcher, "launch_challenge_desk", fake_launch)
    db_path = tmp_path / "missing.db"
    artifacts_root = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        [
            "--db",
            str(db_path),
            "--artifacts-dir",
            str(artifacts_root),
            "challenge",
            "desk",
            "--host",
            "::1",
            "--port",
            "8124",
            "--no-browser",
        ],
    )

    assert result.exit_code == 0, result.stdout
    request = captured["request"]
    assert request.db_path == db_path.resolve()
    assert request.artifacts_root == artifacts_root.resolve()
    assert request.host == "::1"
    assert request.port == 8124
    assert request.no_browser is True
    assert not db_path.exists()
    assert not artifacts_root.exists()


def test_challenge_help_lists_desk():
    result = runner.invoke(app, ["challenge", "--help"])
    assert result.exit_code == 0, result.stdout
    assert "desk" in result.stdout
    assert "local Streamlit Challenge Desk" in result.stdout


def test_cli_desk_maps_launcher_error_without_traceback(monkeypatch):
    def fail_launch(request):
        raise launcher.ChallengeDeskDependencyError(
            f"Install UI with: {launcher.UI_INSTALL_HINT}"
        )

    monkeypatch.setattr(launcher, "launch_challenge_desk", fail_launch)
    result = runner.invoke(app, ["challenge", "desk"])
    assert result.exit_code == 1
    assert launcher.UI_INSTALL_HINT in result.stdout
    assert "Traceback" not in result.stdout


def test_ui_adapter_import_guard():
    forbidden_modules = {
        "sqlite3",
        "ml_saham.cli",
        "ml_saham.data",
        "ml_saham.artifacts",
        "ml_saham.challenge.runner",
        "ml_saham.challenge.metrics",
        "ml_saham.challenge.scorers",
        "ml_saham.challenge.panel",
    }
    violations: list[str] = []
    for source_path in sorted((ROOT / "src" / "ml_saham" / "ui").glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for module in imported:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in forbidden_modules
                ):
                    violations.append(f"{source_path.name}: {module}")
    assert violations == []


def test_streamlit_foundation_shell_apptest(monkeypatch, tmp_path: Path):
    streamlit = pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    db_path = tmp_path / "upstream.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("ML_SAHAM_DB", str(db_path))
    monkeypatch.setenv("ML_SAHAM_ARTIFACTS", str(artifacts_root))
    app_path = ROOT / "src" / "ml_saham" / "ui" / "streamlit_app.py"

    rendered = AppTest.from_file(str(app_path), default_timeout=10).run()

    assert not rendered.exception
    assert rendered.title[0].value == "ml-saham Challenge Desk"
    text = "\n".join(
        element.value
        for collection in (
            rendered.caption,
            rendered.info,
            rendered.warning,
            rendered.text,
            rendered.markdown,
        )
        for element in collection
    )
    assert "read-only" in text.lower() or "Phase 2" in text or "Challenge Desk" in text
    assert str(db_path.resolve()) in text
    assert str(artifacts_root.resolve()) in text
    assert "automatic promotion is disabled" in text
    assert not db_path.exists()
    assert not artifacts_root.exists()
