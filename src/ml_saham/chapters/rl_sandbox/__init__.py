"""Ch.18 RL sandbox — epsilon-greedy bandit (toy, not production)."""

from __future__ import annotations

import math
import random
from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("rl-sandbox")

_EPSILON = 0.15
_N_STEPS = 200
_N_ARMS = 5


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Keputusan berurutan (RL) menarik — tapi di IDX butuh sandbox dulu.",
        "",
        "Opsi pendekatan (sandbox)",
        "  1) Multi-armed bandit epsilon-greedy pada 5 ticker",
        "  2) Reward = daily return historis (replay)",
        "  3) Bandingkan cumulative reward vs random policy",
        "",
        "Caveat",
        "  • SANDBOX / BUKAN live RL production",
        "  • Non-stationary market — bandit assumption lemah",
        "  • Tidak ada scoreboard IHSG (eksplorasi saja)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Appendix tone:",
                "  RL penuh (policy gradient, execution) jauh di luar scope MVP.",
                "  Chapter ini hanya taste-test bandit — lanjut factor/walk-forward dulu.",
            ]
        )
    return "\n".join(lines)


def _daily_returns(conn, tickers: list[str]) -> dict[str, list[float]]:
    candles = load_candles(conn, tickers)
    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))
    out: dict[str, list[float]] = {}
    for t, series in by_t.items():
        series.sort(key=lambda x: x[0])
        closes = [c for _, c in series]
        rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        if len(rets) >= 30:
            out[t] = rets
    return out


def _run_bandit(rets_by_arm: list[list[float]], *, epsilon: float, steps: int, seed: int):
    rng = random.Random(seed)
    n_arms = len(rets_by_arm)
    counts = [0] * n_arms
    values = [0.0] * n_arms
    cum = 0.0
    history = []
    for step in range(steps):
        if rng.random() < epsilon:
            arm = rng.randrange(n_arms)
        else:
            arm = max(range(n_arms), key=lambda i: values[i])
        day = step % min(len(r) for r in rets_by_arm)
        reward = rets_by_arm[arm][day]
        counts[arm] += 1
        values[arm] += (reward - values[arm]) / counts[arm]
        cum += reward
        history.append(reward)
    return cum, values, counts, history


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=20)
        rets_map = _daily_returns(conn, uni)

    tickers = sorted(rets_map, key=lambda t: -len(rets_map[t]))[:_N_ARMS]
    if len(tickers) < _N_ARMS:
        raise ChapterDataError(
            f"Butuh minimal {_N_ARMS} ticker dengan history (ada {len(tickers)})."
        )

    arms = [rets_map[t] for t in tickers]
    cum, values, counts, _ = _run_bandit(
        arms, epsilon=_EPSILON, steps=_N_STEPS, seed=42
    )
    cum_rand, _, _, _ = _run_bandit(arms, epsilon=1.0, steps=_N_STEPS, seed=43)

    # Compute policy action entropy: H(pi) = -sum p_i log2 p_i
    probs = [c / _N_STEPS for c in counts]
    policy_entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(len(tickers))

    lines = [
        ">>> SANDBOX — bukan live RL production <<<",
        f"Arms: {', '.join(tickers)}",
        f"epsilon={_EPSILON}  steps={_N_STEPS}  reward=daily_return replay",
        f"Policy Entropy: {policy_entropy:.3f} / {max_entropy:.3f} bits (lower = higher policy exploitation)",
        "",
        f"Cumulative reward (epsilon-greedy): {cum:+.2%}",
        f"Cumulative reward (random policy):  {cum_rand:+.2%}",
        "",
        "Learned arm values (sample avg):",
    ]
    for i, t in enumerate(tickers):
        lines.append(f"  {t:<6} pulls={counts[i]:3d} ({probs[i]:.1%})  avg_reward={values[i]:+.3%}")

    lines.extend(
        [
            "",
            "Kesimpulan: bandit toy mengajarkan explore/exploit —",
            "bukan bukti edge RL untuk live trading IDX.",
        ]
    )

    metrics = {
        "tickers": tickers,
        "epsilon": _EPSILON,
        "steps": _N_STEPS,
        "cum_reward_greedy": cum,
        "cum_reward_random": cum_rand,
        "policy_entropy_bits": policy_entropy,
        "max_policy_entropy": max_entropy,
        "sandbox": True,
    }
    return DemoResult(
        title="RL sandbox · epsilon-greedy bandit",
        lines=lines,
        metrics=metrics,
        model="epsilon_greedy_bandit",
        summary_md=(
            "# RL sandbox\n\n"
            "Toy bandit on daily returns. NOT production RL.\n"
            f"Greedy cum={cum:+.2%}, random={cum_rand:+.2%}.\n"
        ),
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="— (sandbox only; no production RL engine)",
        bring_back="explore/exploit intuition — lanjut walk-forward / pipeline dulu",
    )
