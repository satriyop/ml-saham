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
    ChapterMeta(8, "survival-analysis", "Memprediksi waktu reaksi harga (Survival Analysis)", "Hard", "phase2", "phase2"),
    ChapterMeta(9, "volume-anomaly", "Volume & lonjakan tidak biasa", "Medium", "v1_1", "v1_1"),
    ChapterMeta(10, "headline-tone", "Membaca berita singkat", "Medium", "phase2", "mvp"),
    ChapterMeta(11, "volatility-sizing", "Volatilitas & ukuran posisi", "Medium", "phase2", "mvp"),
    ChapterMeta(12, "market-regime", "Rezim pasar", "Hard", "phase2", "phase2"),
    ChapterMeta(13, "walk-forward", "Prediksi multi-fitur + walk-forward", "Hard", "phase2", "phase2"),
    ChapterMeta(14, "portfolio-small", "Membangun portofolio kecil", "Hard", "phase2", "mvp"),
    ChapterMeta(15, "corp-events", "Peristiwa korporasi massal", "Hard", "phase2", "phase2"),
    ChapterMeta(16, "earnings-surprise", "Earnings surprise", "Hard", "phase2", "phase2"),
    ChapterMeta(17, "nowcasting", "Nowcasting fundamental (Mixed-Frequency)", "Hard", "phase2", "phase2"),
    ChapterMeta(18, "pre-open-rank", "Peringkat menjelang pembukaan", "Hard", "phase2", "phase2"),
    ChapterMeta(19, "research-pipeline", "Pipeline riset ujung-ke-ujung", "Complex", "phase2", "phase2"),
    ChapterMeta(20, "rl-sandbox", "Sandbox keputusan berurutan (opsional)", "Complex", "optional", "mvp"),
    ChapterMeta(21, "seasonality-drift", "Efek musiman & anomali kalender", "Hard", "phase2", "phase2"),
    ChapterMeta(22, "analyst-consensus", "Konsensus analis & revisi target harga", "Hard", "phase2", "phase2"),
    ChapterMeta(23, "broker-accumulation", "Akumulasi broker top-N & konsentrasi kepemilikan", "Hard", "phase2", "phase2"),
    ChapterMeta(24, "broker-network", "Deteksi sindikasi broker (Graph ML)", "Complex", "phase2", "phase2"),
    ChapterMeta(25, "sector-breadth", "Partisipasi pasar & rotasi sektor", "Hard", "phase2", "mvp"),
    ChapterMeta(26, "volatility-squeeze", "Kompresi volatilitas & klasifikasi breakout", "Hard", "phase2", "mvp"),
    ChapterMeta(27, "relative-strength", "Relative strength Mansfield vs IHSG", "Hard", "phase2", "mvp"),
    ChapterMeta(28, "financial-quality", "Skor kualitas akuntansi Piotroski F-Score", "Hard", "phase2", "phase2"),
    ChapterMeta(29, "financial-distress", "Model kebangkrutan Altman Z-Score", "Hard", "phase2", "phase2"),
    ChapterMeta(30, "ichimoku-cloud", "Klasifikasi breakout awan Kumo Ichimoku", "Hard", "phase2", "mvp"),
    ChapterMeta(31, "bandar-detector", "Klasifikasi sinyal akumulasi broker bandar", "Hard", "phase2", "phase2"),
    ChapterMeta(32, "forward-valuation", "Valuasi konsensus Forward P/E & rasio PEG", "Hard", "phase2", "phase2"),
    ChapterMeta(33, "special-monitoring", "Notasi khusus bursa, UMA & risiko likuiditas", "Hard", "phase2", "phase2"),
    ChapterMeta(34, "earnings-quality", "Anomali akrual Sloan & kualitas laba", "Hard", "phase2", "phase2"),
    ChapterMeta(35, "microstructure-impact", "Ilikuiditas Amihud & dampak harga mikrostruk", "Hard", "phase2", "phase2"),
    ChapterMeta(36, "meta-ensemble", "Super learner ensemble multi-faktor terstack", "Complex", "phase2", "mvp"),
    ChapterMeta(37, "accum-policy", "Menantang pembobotan statis AccumScorePolicy (Per-factor)", "Hard", "phase2", "phase2"),
    ChapterMeta(38, "pre-open-heuristic", "Menantang aturan batas dan Raw Score Pre-Open", "Hard", "phase2", "phase2"),
    ChapterMeta(39, "accum-macro", "Menantang penggabungan makro: Signal x Market x Risk", "Hard", "phase2", "phase2"),
    ChapterMeta(40, "accum-deep", "Deep Fingerprint Mining: XGBoost pada 100+ Fitur", "Hard", "phase2", "phase2"),
    ChapterMeta(41, "pre-open-direction", "Pre-open Modul Arah (Direction)", "Hard", "phase2", "phase2"),
    ChapterMeta(42, "pre-open-participation", "Pre-open Modul Partisipasi (Spoofing)", "Hard", "phase2", "phase2"),
    ChapterMeta(43, "pre-open-auction", "Pre-open Modul Auction Quality", "Hard", "phase2", "phase2"),
    ChapterMeta(44, "pre-open-macro", "Pre-open Modul Keseluruhan (Full)", "Hard", "phase2", "phase2"),
    ChapterMeta(
        45,
        "data-integrity",
        "Integritas data plane & kesehatan observation (challenge gate)",
        "Medium",
        "phase2",
        "mvp",
    ),
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
