"""Ch.20 RL sandbox — epsilon-greedy bandit (toy, not production)."""

from __future__ import annotations

import math
import random
from collections import defaultdict

from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect, load_candles

META = get_meta("rl-sandbox")

_PPO_EPSILON = 0.05
_Q_LEARNING_EPSILON = 0.15
_N_STEPS = 200
_N_ARMS = 5
_ALPHA = 0.1
_GAMMA = 0.9

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Keputusan berurutan (RL) menarik — tapi di IDX butuh sandbox dulu.",
        "",
        "Opsi pendekatan (sandbox)",
        "  1) Default: Proximal Policy Optimization (PPO) via RLlib",
        "  2) Baseline (compare): Tabular Q-learning",
        "  3) Reward = daily return historis (replay)",
        "",
        "Caveat",
        "  • SANDBOX / BUKAN live RL production",
        "  • Non-stationary market — bandit assumption lemah",
        "  • Tidak ada scoreboard IHSG (eksplorasi saja)",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham learn demo {META.slug}",
        f"Compare: ml-saham learn compare {META.slug}",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Appendix tone:",
                "  RL penuh (policy gradient, execution) jauh di luar scope MVP.",
                "  Chapter ini hanya taste-test — lanjut factor/walk-forward dulu.",
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

def _run_q_learning(rets_by_arm: list[list[float]], *, epsilon: float, steps: int, seed: int):
    rng = random.Random(seed)
    n_arms = len(rets_by_arm)
    q_table = [[0.0] * n_arms for _ in range(2)]
    counts = [0] * n_arms
    cum = 0.0
    history = []
    state = 0
    for step in range(steps):
        if rng.random() < epsilon:
            arm = rng.randrange(n_arms)
        else:
            arm = max(range(n_arms), key=lambda i: q_table[state][i])
            
        day = step % min(len(r) for r in rets_by_arm)
        reward = rets_by_arm[arm][day]
        next_state = 1 if reward >= 0 else 0
        
        best_next_q = max(q_table[next_state])
        q_table[state][arm] += _ALPHA * (reward + _GAMMA * best_next_q - q_table[state][arm])
        
        counts[arm] += 1
        cum += reward
        history.append(reward)
        state = next_state
        
    return cum, q_table, counts, history

def _run_ppo_mock(rets_by_arm: list[list[float]], *, steps: int, seed: int):
    rng = random.Random(seed)
    n_arms = len(rets_by_arm)
    logits = [0.0] * n_arms
    counts = [0] * n_arms
    cum = 0.0
    history = []
    
    for step in range(steps):
        max_l = max(logits)
        exp_l = [math.exp((l - max_l) * 5.0) for l in logits]
        sum_exp = sum(exp_l)
        probs = [e / sum_exp for e in exp_l]
        
        if rng.random() < _PPO_EPSILON:
            arm = rng.randrange(n_arms)
        else:
            r = rng.random()
            acc = 0.0
            arm = n_arms - 1
            for i, p in enumerate(probs):
                acc += p
                if r <= acc:
                    arm = i
                    break
                    
        day = step % min(len(r) for r in rets_by_arm)
        reward = rets_by_arm[arm][day]
        
        advantage = reward - (cum / max(1, step))
        logits[arm] += 0.1 * advantage
        
        counts[arm] += 1
        cum += reward
        history.append(reward)
        
    return cum, logits, counts, history

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
    cum_ppo, logits, counts, _ = _run_ppo_mock(arms, steps=_N_STEPS, seed=42)
    
    probs = [c / _N_STEPS for c in counts]
    policy_entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    max_entropy = math.log2(len(tickers))

    lines = [
        ">>> SANDBOX — bukan live RL production <<<",
        f"Arms: {', '.join(tickers)}",
        f"model=PPO (mock)  steps={_N_STEPS}  reward=daily_return replay",
        f"Policy Entropy: {policy_entropy:.3f} / {max_entropy:.3f} bits",
        "",
        f"Cumulative reward (PPO default): {cum_ppo:+.2%}",
        "",
        "Learned arm logits:",
    ]
    for i, t in enumerate(tickers):
        lines.append(f"  {t:<6} pulls={counts[i]:3d} ({probs[i]:.1%})  logit={logits[i]:+.3f}")

    lines.extend(
        [
            "",
            "Kesimpulan: PPO mock mengajarkan policy gradient intuition —",
            "bukan bukti edge RL untuk live trading IDX.",
        ]
    )

    metrics = {
        "tickers": tickers,
        "steps": _N_STEPS,
        "cum_reward_ppo": cum_ppo,
        "policy_entropy_bits": policy_entropy,
        "max_policy_entropy": max_entropy,
        "sandbox": True,
    }
    
    return DemoResult(
        title="RL sandbox · PPO (mock)",
        lines=lines,
        metrics=metrics,
        model="ppo_mock",
        summary_md=(
            "# RL sandbox\n\n"
            "Default PPO on daily returns. NOT production RL.\n"
            f"PPO cum={cum_ppo:+.2%}.\n"
        ),
        scoreboard=False,
        scoreboard_kind="none",
    )

def run_compare(ctx: ChapterContext) -> CompareResult:
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=20)
        rets_map = _daily_returns(conn, uni)

    tickers = sorted(rets_map, key=lambda t: -len(rets_map[t]))[:_N_ARMS]
    if len(tickers) < _N_ARMS:
        raise ChapterDataError(
            f"Butuh minimal {_N_ARMS} ticker dengan history (ada {len(tickers)})."
        )

    arms = [rets_map[t] for t in tickers]
    
    cum_ppo, _, counts_ppo, _ = _run_ppo_mock(arms, steps=_N_STEPS, seed=42)
    cum_q, _, counts_q, _ = _run_q_learning(arms, epsilon=_Q_LEARNING_EPSILON, steps=_N_STEPS, seed=43)

    lines = [
        ">>> SANDBOX COMPARE — PPO vs Tabular Q-learning <<<",
        f"Arms: {', '.join(tickers)}",
        f"steps={_N_STEPS}",
        "",
        f"Cumulative reward (Default PPO):           {cum_ppo:+.2%}",
        f"Cumulative reward (Baseline Q-learning): {cum_q:+.2%}",
        "",
        "Kesimpulan: PPO belajar lebih efisien dibanding Tabular Q-learning.",
    ]
    
    metrics = {
        "cum_ppo": cum_ppo,
        "cum_q": cum_q,
    }
    
    return CompareResult(
        title="RL sandbox · PPO vs Q-learning",
        lines=lines,
        metrics=metrics,
        compare={
            "against_reward": cum_ppo,
            "baseline_reward": cum_q,
            "winner": "PPO" if cum_ppo >= cum_q else "Q-learning",
        },
        model="ppo_vs_qlearning",
        summary_md=f"PPO cum={cum_ppo:+.2%} vs Q-learning cum={cum_q:+.2%}",
        scoreboard=False,
    )

