"""Artifact pack writer — schema in artifacts.md."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
ENV_ARTIFACTS = "ML_SAHAM_ARTIFACTS"
DEFAULT_ARTIFACTS_DIR = Path("artifacts")
JAKARTA = ZoneInfo("Asia/Jakarta")


def resolve_artifacts_root(cli_path: Path | None = None) -> Path:
    if cli_path is not None:
        return Path(cli_path).expanduser().resolve()
    env = os.environ.get(ENV_ARTIFACTS)
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / DEFAULT_ARTIFACTS_DIR).resolve()


def _slug_ts(when: datetime | None = None) -> str:
    dt = when or datetime.now(tz=JAKARTA)
    return dt.strftime("%Y%m%d_%H%M%S")


@dataclass
class ScoreboardMeta:
    type: str = "long_only_vs_ihsg"
    costs: str = "gross_banner"
    disclaimer: str = "bukan_saran"

    def as_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "costs": self.costs,
            "disclaimer": self.disclaimer,
        }


@dataclass
class ArtifactWriteRequest:
    topic: str
    chapter: int
    mode: str  # demo | compare | deepdive
    db_path: Path | str
    universe: str = "LQ45"
    as_of: str | None = None
    model: str | None = None
    scoreboard: ScoreboardMeta = field(default_factory=ScoreboardMeta)
    ai_saham_deepdive: bool = False
    summary_md: str = ""
    metrics: dict[str, Any] | None = None
    compare: dict[str, Any] | None = None
    suggestions_md: str | None = None
    extra_files: dict[str, str | bytes] = field(default_factory=dict)
    created_at: datetime | None = None
    pack_slug: str | None = None


@dataclass(frozen=True)
class ArtifactPack:
    path: Path
    manifest: dict[str, Any]

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest.json"


def write_artifact_pack(
    request: ArtifactWriteRequest,
    *,
    artifacts_root: Path | None = None,
) -> ArtifactPack:
    """Write manifest.json + summary.md (+ metrics/compare/suggestions)."""
    root = artifacts_root if artifacts_root is not None else resolve_artifacts_root()
    created = request.created_at or datetime.now(tz=JAKARTA)
    pack_name = request.pack_slug or f"{_slug_ts(created)}_{request.mode}"
    pack_dir = root / request.topic / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)

    files: list[str] = []

    summary = request.summary_md.strip() or _default_summary(request)
    (pack_dir / "summary.md").write_text(summary + "\n", encoding="utf-8")
    files.append("summary.md")

    if request.metrics is not None:
        (pack_dir / "metrics.json").write_text(
            json.dumps(request.metrics, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        files.append("metrics.json")

    if request.compare is not None:
        (pack_dir / "compare.json").write_text(
            json.dumps(request.compare, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        files.append("compare.json")

    if request.suggestions_md is not None:
        (pack_dir / "suggestions.md").write_text(
            request.suggestions_md.rstrip() + "\n",
            encoding="utf-8",
        )
        files.append("suggestions.md")

    for name, content in request.extra_files.items():
        # basename only — avoid path traversal
        safe = Path(name).name
        target = pack_dir / safe
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
        files.append(safe)

    as_of = request.as_of or created.date().isoformat()
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "topic": request.topic,
        "chapter": request.chapter,
        "created_at": created.isoformat(),
        "db_path": str(Path(request.db_path)),
        "universe": request.universe,
        "as_of": as_of,
        "mode": request.mode,
        "model": request.model,
        "scoreboard": request.scoreboard.as_dict(),
        "ai_saham_deepdive": request.ai_saham_deepdive,
        "files": files,
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ArtifactPack(path=pack_dir, manifest=manifest)


def _default_summary(request: ArtifactWriteRequest) -> str:
    return (
        f"# {request.topic} · {request.mode}\n\n"
        f"Chapter {request.chapter}. Stub / otomatis — lihat metrics.json.\n\n"
        "## Caveat\n\n"
        "- Bukan saran trading / investasi.\n"
        "- Skorboard long-only vs IHSG; cek banner biaya di CLI.\n"
    )


def stub_demo_metrics(*, with_costs: bool = False) -> dict[str, Any]:
    """Deterministic toy metrics so Phase 2 demos write a valid pack."""
    # Monotone-ish scores vs noisy returns → modest positive IC
    scores = [float(i) for i in range(1, 21)]
    returns = [0.01 * ((i % 5) - 2) + 0.002 * i for i in range(1, 21)]
    if with_costs:
        from ml_saham.eval.costs import apply_haircut

        returns = apply_haircut(returns)
    from ml_saham.eval.metrics import metrics_bundle

    bundle = metrics_bundle(
        scores,
        returns,
        benchmark_return=0.01,
        date_range=("stub", "stub"),
        n_tickers=20,
    )
    bundle["stub"] = True
    bundle["note"] = "Phase 2 stub metrics — diganti chapter real di Phase 3"
    return bundle
