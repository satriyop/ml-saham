"""Optional simple cost haircut for scoreboard honesty demos."""

from __future__ import annotations

from collections.abc import Sequence

# Default round-trip haircut for teaching demos (not a brokerage quote).
DEFAULT_ROUNDTRIP_BPS = 20.0


def bps_to_fraction(bps: float) -> float:
    return bps / 10_000.0


def apply_haircut(
    returns: Sequence[float],
    *,
    roundtrip_bps: float = DEFAULT_ROUNDTRIP_BPS,
) -> list[float]:
    """Subtract a flat round-trip fraction from each return."""
    haircut = bps_to_fraction(roundtrip_bps)
    return [float(r) - haircut for r in returns]


def costs_label(*, with_costs: bool) -> str:
    """Value for manifest scoreboard.costs."""
    return "simple_haircut" if with_costs else "gross_banner"
