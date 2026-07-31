"""Smoke: check_challenge_contracts.sh is executable and exits 0."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_challenge_contracts.sh"


def test_check_challenge_contracts_script_passes():
    assert SCRIPT.is_file()
    env = {**os.environ, "PYTHONPATH": f"src{os.pathsep}."}
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stdout + "\n" + r.stderr
    assert "PASS" in r.stdout
