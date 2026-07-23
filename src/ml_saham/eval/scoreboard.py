"""Scoreboard helpers and honesty banners."""

from __future__ import annotations

from dataclasses import dataclass


DISCLAIMER_ID = "Bukan saran trading / investasi"
COSTS_BANNER_ID = "Skorboard: long-only vs IHSG · belum termasuk biaya"
COSTS_WITH_HAIRCUT_ID = "Skorboard: long-only vs IHSG · dengan haircut biaya sederhana"


@dataclass(frozen=True)
class ScoreboardBanners:
    lines: tuple[str, ...]

    def render(self) -> str:
        return "\n".join(f"⚠ {line}" for line in self.lines)


def default_banners(*, with_costs: bool = False) -> ScoreboardBanners:
    cost = COSTS_WITH_HAIRCUT_ID if with_costs else COSTS_BANNER_ID
    return ScoreboardBanners(lines=(cost, DISCLAIMER_ID))


def open_session_banners(*, with_costs: bool = False) -> ScoreboardBanners:
    cost = (
        "Skorboard: open-session · dengan haircut biaya sederhana"
        if with_costs
        else "Skorboard: open-session · belum termasuk biaya"
    )
    return ScoreboardBanners(lines=(cost, DISCLAIMER_ID))
