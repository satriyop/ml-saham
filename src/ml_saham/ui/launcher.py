"""Stable launcher boundary for the optional local Streamlit adapter."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UI_INSTALL_HINT = 'pip install -e ".[ui]"'
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ChallengeDeskLaunchError(RuntimeError):
    """Base error for a launcher failure before Streamlit owns the process."""


class ChallengeDeskDependencyError(ChallengeDeskLaunchError):
    """Raised when the optional UI dependency is not installed."""


@dataclass(frozen=True)
class ChallengeDeskLaunchRequest:
    """Immutable launcher request; it carries no challenge product decisions."""

    db_path: Path
    artifacts_root: Path
    host: str = "127.0.0.1"
    port: int = 8501
    no_browser: bool = False


def normalize_loopback_host(host: str) -> str:
    """Accept named loopback aliases but never a remote/wildcard bind."""
    normalized = host.strip().lower()
    if normalized not in LOOPBACK_HOSTS:
        raise ChallengeDeskLaunchError(
            "Challenge Desk is local-only; --host must be 127.0.0.1, localhost, or ::1"
        )
    return normalized


def streamlit_app_path() -> Path:
    """Return the packaged Streamlit entrypoint without importing Streamlit."""
    return Path(__file__).with_name("streamlit_app.py").resolve()


def build_streamlit_command(request: ChallengeDeskLaunchRequest) -> list[str]:
    """Build the official Streamlit CLI argv; never route through a shell."""
    if not 1 <= request.port <= 65535:
        raise ChallengeDeskLaunchError("Challenge Desk port must be between 1 and 65535")
    host = normalize_loopback_host(request.host)
    app_path = streamlit_app_path()
    if not app_path.is_file():
        raise ChallengeDeskLaunchError(
            f"Packaged Challenge Desk entrypoint is missing: {app_path}"
        )
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(request.port),
        "--server.headless",
        "true" if request.no_browser else "false",
        "--browser.gatherUsageStats",
        "false",
    ]


def _normalized_exit_code(returncode: int) -> int:
    if returncode >= 0:
        return returncode
    return min(255, 128 + abs(returncode))


def launch_challenge_desk(
    request: ChallengeDeskLaunchRequest,
    *,
    find_spec: Callable[[str], Any] = importlib.util.find_spec,
    run_process: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> int:
    """Launch Streamlit and return its process status.

    Dependency discovery happens lazily so core/headless imports do not require
    Streamlit. The child receives explicit paths through the existing public
    environment contract; no upstream file is opened by this launcher.
    """
    if find_spec("streamlit") is None:
        raise ChallengeDeskDependencyError(
            f"Challenge Desk requires the optional UI dependency. Install it with: {UI_INSTALL_HINT}"
        )

    command = build_streamlit_command(request)
    child_env = os.environ.copy()
    child_env["ML_SAHAM_DB"] = str(request.db_path)
    child_env["ML_SAHAM_ARTIFACTS"] = str(request.artifacts_root)
    try:
        completed = run_process(command, env=child_env, check=False)
    except OSError as exc:
        raise ChallengeDeskLaunchError(f"Unable to start Challenge Desk: {exc}") from exc
    return _normalized_exit_code(int(completed.returncode))
