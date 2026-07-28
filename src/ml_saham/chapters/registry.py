"""Chapter registry — topic slug → metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterMeta:
    number: int
    slug: str
    title: str
    tier: str
    phase: str  # mvp | v1_1 | phase2 | optional
    required_data: str  # mvp | v1_1 | phase2


# Titles (ID) aligned with chapters.md / ux.md topic slugs.
CHAPTERS: tuple[ChapterMeta, ...] = (
    ChapterMeta(0, "orientasi", "Orientasi — cara menilai hasil tanpa menipu diri", "—", "mvp", "mvp"),
    ChapterMeta(1, "clean-prices", "Membersihkan harga saham", "Simple", "mvp", "mvp"),
    ChapterMeta(2, "screen-rules", "Saring saham dengan aturan", "Simple", "mvp", "mvp"),
    ChapterMeta(3, "pattern-fail", "Mengenali pola harga sederhana (failure lab)", "Simple", "mvp", "mvp"),
    ChapterMeta(4, "factor-score", "Skor faktor: value, momentum, quality", "Medium", "mvp", "mvp"),
    ChapterMeta(5, "cluster-peers", "Mengelompokkan saham yang bergerak mirip", "Medium", "v1_1", "v1_1"),
    ChapterMeta(6, "broker-flow", "Aliran broker & asing", "Medium", "mvp", "mvp"),
    ChapterMeta(7, "insider", "Aktivitas insider", "Medium", "v1_1", "v1_1"),
    ChapterMeta(8, "volume-anomaly", "Volume & lonjakan tidak biasa", "Medium", "v1_1", "v1_1"),
    ChapterMeta(9, "headline-tone", "Membaca berita singkat", "Medium", "phase2", "mvp"),
    ChapterMeta(10, "volatility-sizing", "Volatilitas & ukuran posisi", "Medium", "phase2", "mvp"),
    ChapterMeta(11, "market-regime", "Rezim pasar", "Hard", "phase2", "phase2"),
    ChapterMeta(12, "walk-forward", "Prediksi multi-fitur + walk-forward", "Hard", "phase2", "phase2"),
    ChapterMeta(13, "portfolio-small", "Membangun portofolio kecil", "Hard", "phase2", "mvp"),
    ChapterMeta(14, "corp-events", "Peristiwa korporasi massal", "Hard", "phase2", "phase2"),
    ChapterMeta(15, "earnings-surprise", "Earnings surprise", "Hard", "phase2", "phase2"),
    ChapterMeta(16, "pre-open-rank", "Peringkat menjelang pembukaan", "Hard", "phase2", "phase2"),
    ChapterMeta(17, "research-pipeline", "Pipeline riset ujung-ke-ujung", "Complex", "phase2", "phase2"),
    ChapterMeta(18, "rl-sandbox", "Sandbox keputusan berurutan (opsional)", "Complex", "optional", "mvp"),
    ChapterMeta(19, "seasonality-drift", "Efek musiman & anomali kalender", "Hard", "phase2", "phase2"),
    ChapterMeta(20, "analyst-consensus", "Konsensus analis & revisi target harga", "Hard", "phase2", "phase2"),
    ChapterMeta(21, "broker-accumulation", "Akumulasi broker top-N & konsentrasi kepemilikan", "Hard", "phase2", "phase2"),
    ChapterMeta(22, "sector-breadth", "Partisipasi pasar & rotasi sektor", "Hard", "phase2", "mvp"),
    ChapterMeta(23, "volatility-squeeze", "Kompresi volatilitas & klasifikasi breakout", "Hard", "phase2", "mvp"),
    ChapterMeta(24, "relative-strength", "Relative strength Mansfield vs IHSG", "Hard", "phase2", "mvp"),
    ChapterMeta(25, "financial-quality", "Skor kualitas akuntansi Piotroski F-Score", "Hard", "phase2", "phase2"),
    ChapterMeta(26, "financial-distress", "Model kebangkrutan Altman Z-Score", "Hard", "phase2", "phase2"),
    ChapterMeta(27, "ichimoku-cloud", "Klasifikasi breakout awan Kumo Ichimoku", "Hard", "phase2", "mvp"),
    ChapterMeta(28, "bandar-detector", "Klasifikasi sinyal akumulasi broker bandar", "Hard", "phase2", "phase2"),
    ChapterMeta(29, "forward-valuation", "Valuasi konsensus Forward P/E & rasio PEG", "Hard", "phase2", "phase2"),
)

_BY_SLUG = {c.slug: c for c in CHAPTERS}


def get(slug: str) -> ChapterMeta:
    try:
        return _BY_SLUG[slug]
    except KeyError as exc:
        known = ", ".join(c.slug for c in CHAPTERS)
        raise KeyError(f"Topic tidak dikenal: {slug!r}. Dikenal: {known}") from exc


def all_chapters() -> tuple[ChapterMeta, ...]:
    return CHAPTERS


def mvp_chapters() -> tuple[ChapterMeta, ...]:
    return tuple(c for c in CHAPTERS if c.phase == "mvp")


def v1_1_chapters() -> tuple[ChapterMeta, ...]:
    return tuple(c for c in CHAPTERS if c.phase == "v1_1")


def phase2_chapters() -> tuple[ChapterMeta, ...]:
    return tuple(c for c in CHAPTERS if c.phase == "phase2")


def optional_chapters() -> tuple[ChapterMeta, ...]:
    return tuple(c for c in CHAPTERS if c.phase == "optional")


def known_slugs() -> list[str]:
    return [c.slug for c in CHAPTERS]
