"""Structural + dry-run checks for weekly health cron install scripts."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_cron_scripts_exist_and_executable():
    for name in (
        "challenge_health_weekly.sh",
        "install_challenge_health_cron.sh",
        "uninstall_challenge_health_cron.sh",
    ):
        p = SCRIPTS / name
        assert p.is_file(), p
        mode = p.stat().st_mode
        assert mode & stat.S_IXUSR, f"{name} not user-executable"
        text = p.read_text(encoding="utf-8")
        assert "ml-saham" in text
        if "weekly" in name:
            assert "--with-diagnostics" in text
        if "install" in name:
            assert "crontab" in text
            assert "ml-saham-challenge-health-weekly" in text


def test_weekly_script_help_or_missing_db_is_honest(tmp_path: Path):
    """Without a real DB, job should fail honestly (exit 2), not traceback."""
    env = os.environ.copy()
    env["ML_SAHAM_ROOT"] = str(ROOT)
    env["ML_SAHAM_DB"] = str(tmp_path / "missing.db")
    env["ML_SAHAM_ARTIFACTS"] = str(tmp_path / "arts")
    r = subprocess.run(
        [str(SCRIPTS / "challenge_health_weekly.sh")],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert r.returncode == 2
    assert "DB missing" in r.stdout or "DB missing" in r.stdout + r.stderr
