"""Phase 0 smoke tests."""

from pathlib import Path

from ml_saham.chapters import get, mvp_chapters
from ml_saham.chapters.loader import has_chapter_module, load_chapter
from ml_saham.chapters.registry import all_chapters
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


def test_registry_loader_parity():
    """Every registered chapter must be loadable; META number matches registry."""
    missing = [c.slug for c in all_chapters() if not has_chapter_module(c.slug)]
    assert missing == [], f"registry slugs missing from loader: {missing}"

    for c in all_chapters():
        mod = load_chapter(c.slug)
        assert hasattr(mod, "META"), c.slug
        assert mod.META.number == c.number, (c.slug, mod.META.number, c.number)
        assert mod.META.slug == c.slug


def test_formerly_orphaned_chapters_loadable():
    for slug, number in (
        ("survival-analysis", 8),
        ("nowcasting", 17),
        ("broker-network", 24),
        ("volume-anomaly", 9),
        ("headline-tone", 10),
        ("pre-open-rank", 18),
    ):
        ch = get(slug)
        assert ch.number == number
        assert has_chapter_module(slug)
        assert load_chapter(slug).META.number == number


def test_resolve_db_default(monkeypatch):
    monkeypatch.delenv("ML_SAHAM_DB", raising=False)
    assert resolve_db_path(None) == DEFAULT_DB.expanduser().resolve()


def test_resolve_db_cli(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ML_SAHAM_DB", raising=False)
    p = tmp_path / "data.db"
    p.touch()
    assert resolve_db_path(p) == p.resolve()
