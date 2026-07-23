"""Ranking and return metrics (stdlib only — no pandas required)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any


def _validate_pairs(
    scores: Sequence[float],
    returns: Sequence[float],
) -> tuple[list[float], list[float]]:
    if len(scores) != len(returns):
        raise ValueError(
            f"scores/returns length mismatch: {len(scores)} vs {len(returns)}"
        )
    xs: list[float] = []
    ys: list[float] = []
    for s, r in zip(scores, returns, strict=True):
        if s is None or r is None:
            continue
        if isinstance(s, float) and math.isnan(s):
            continue
        if isinstance(r, float) and math.isnan(r):
            continue
        xs.append(float(s))
        ys.append(float(r))
    if len(xs) < 2:
        raise ValueError("need at least 2 finite score/return pairs")
    return xs, ys


def average_ranks(values: Sequence[float]) -> list[float]:
    """Competition ranks with averages for ties (1-based)."""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks = [0.0] * len(values)
    i = 0
    n = len(indexed)
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        # ranks i..j (0-based positions) → average of (i+1)..(j+1)
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n != len(ys) or n < 2:
        raise ValueError("pearson needs equal-length sequences with n>=2")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return float("nan")
    return num / (den_x * den_y)


def rank_ic(scores: Sequence[float], returns: Sequence[float]) -> float:
    """Spearman rank IC: Pearson correlation of average ranks."""
    xs, ys = _validate_pairs(scores, returns)
    return pearson(average_ranks(xs), average_ranks(ys))


@dataclass(frozen=True)
class BucketReturn:
    bucket: int  # 1 = lowest scores … n_buckets = highest
    n: int
    mean_return: float
    mean_vs_benchmark: float | None = None


def bucket_returns(
    scores: Sequence[float],
    returns: Sequence[float],
    *,
    n_buckets: int = 5,
    benchmark_return: float | None = None,
) -> list[BucketReturn]:
    """Mean forward return by score quantile (1=low … n_buckets=high)."""
    if n_buckets < 2:
        raise ValueError("n_buckets must be >= 2")
    xs, ys = _validate_pairs(scores, returns)
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    # split into roughly equal buckets along sorted scores
    buckets: list[list[float]] = [[] for _ in range(n_buckets)]
    for rank_i, idx in enumerate(order):
        # map rank position to bucket
        b = min(n_buckets - 1, (rank_i * n_buckets) // len(order))
        buckets[b].append(ys[idx])

    out: list[BucketReturn] = []
    for b_i, vals in enumerate(buckets, start=1):
        if not vals:
            mean = float("nan")
            vs = None
        else:
            mean = sum(vals) / len(vals)
            vs = (
                mean - benchmark_return
                if benchmark_return is not None
                else None
            )
        out.append(
            BucketReturn(
                bucket=b_i,
                n=len(vals),
                mean_return=mean,
                mean_vs_benchmark=vs,
            )
        )
    return out


def top_quantile_return(
    scores: Sequence[float],
    returns: Sequence[float],
    *,
    quantile: float = 0.2,
    benchmark_return: float | None = None,
) -> dict[str, Any]:
    """Mean return of the top score quantile (default top 20%)."""
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be in (0, 1]")
    xs, ys = _validate_pairs(scores, returns)
    order = sorted(range(len(xs)), key=lambda i: xs[i], reverse=True)
    k = max(1, int(math.ceil(len(order) * quantile)))
    chosen = [ys[i] for i in order[:k]]
    mean = sum(chosen) / len(chosen)
    result: dict[str, Any] = {
        "quantile": quantile,
        "n": len(chosen),
        "mean_return": mean,
    }
    if benchmark_return is not None:
        result["mean_vs_benchmark"] = mean - benchmark_return
        result["benchmark_return"] = benchmark_return
    return result


def metrics_bundle(
    scores: Sequence[float],
    returns: Sequence[float],
    *,
    n_buckets: int = 5,
    top_quantile: float = 0.2,
    benchmark_return: float | None = None,
    date_range: tuple[str | None, str | None] | None = None,
    n_tickers: int | None = None,
) -> dict[str, Any]:
    """Standard demo/compare metrics payload for artifacts."""
    xs, ys = _validate_pairs(scores, returns)
    buckets = bucket_returns(
        xs, ys, n_buckets=n_buckets, benchmark_return=benchmark_return
    )
    top = top_quantile_return(
        xs, ys, quantile=top_quantile, benchmark_return=benchmark_return
    )
    payload: dict[str, Any] = {
        "rank_ic": rank_ic(xs, ys),
        "n": len(xs),
        "n_tickers": n_tickers if n_tickers is not None else len(xs),
        "buckets": [asdict(b) for b in buckets],
        "top_quantile": top,
    }
    if date_range is not None:
        payload["date_range"] = {"start": date_range[0], "end": date_range[1]}
    if benchmark_return is not None:
        payload["benchmark_return"] = benchmark_return
    return payload
