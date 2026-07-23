"""Phase 0 smoke tests."""

from pathlib import Path

from ml_saham.chapters import get, mvp_chapters
from ml_saham.data.connection import DEFAULT_DB, resolve_db_path


def test_mvp_slugs():
    slugs = {c.slug for c in mvp_chapters()}
    assert slugs == {
        "orientasi",
        "clean-prices",
        "screen-rules",
        "pattern-fail",
        "factor-score",
        "broker-flow",
    }


def test_get_chapter():
    ch = get("factor-score")
    assert ch.number == 4
    assert ch.phase == "mvp"


def test_resolve_db_default(monkeypatch):
    monkeypatch.delenv("ML_SAHAM_DB", raising=False)
    assert resolve_db_path(None) == DEFAULT_DB.expanduser().resolve()


def test_resolve_db_cli(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ML_SAHAM_DB", raising=False)
    p = tmp_path / "data.db"
    p.touch()
    assert resolve_db_path(p) == p.resolve()
