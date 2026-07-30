"""Policy scorers for accum weight tournament and pre-open rank."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import numpy as np

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.types import PolicySnapshot


def enabled_keys(policy: PolicySnapshot) -> list[str]:
    return [c.key for c in policy.enabled_components()]


def score_production(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Production score by score_kind."""
    if policy.score_kind == "rank_primary":
        return [float(r.components.get("official_rank_score", 0.0)) for r in rows]
    if policy.score_kind == "raw_score_primary":
        return [float(r.components.get("production_raw_score", 0.0)) for r in rows]
    if policy.score_kind == "gate_block":
        # 1.0 = allowed (open), 0.0 = blocked by any enabled gate
        keys = enabled_keys(policy)
        out: list[float] = []
        for r in rows:
            blocked = any(float(r.components.get(k, 0.0)) > 0.0 for k in keys)
            out.append(0.0 if blocked else 1.0)
        return out
    keys = enabled_keys(policy)
    return [float(sum(r.components.get(k, 0.0) for k in keys)) for r in rows]


def score_gate_off(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Challenger: never block — all names allowed (1.0)."""
    del policy
    return [1.0] * len(rows)


def mean_excess_allowed(
    rows: Sequence[PanelRow],
    allow_scores: Sequence[float],
    primary_horizon: int,
) -> tuple[float | None, float, int]:
    """Mean excess among allowed rows (score > 0.5). Returns (mean, block_rate, n_open)."""
    ys: list[float] = []
    n_block = 0
    for r, s in zip(rows, allow_scores, strict=True):
        if float(s) > 0.5:
            if primary_horizon in r.excess:
                ys.append(float(r.excess[primary_horizon]))
        else:
            n_block += 1
    n = len(rows)
    block_rate = (n_block / n) if n else 0.0
    if len(ys) < 2:
        return None, block_rate, len(ys)
    return float(sum(ys) / len(ys)), block_rate, len(ys)


def score_production_drop(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
    factor_key: str,
) -> list[float]:
    """Production score with factor_key zeroed (ablation)."""
    keys = enabled_keys(policy)
    if factor_key not in keys:
        raise KeyError(f"factor {factor_key!r} not in enabled production sleeves")
    out: list[float] = []
    for r in rows:
        s = 0.0
        for k in keys:
            if k == factor_key:
                continue
            s += r.components.get(k, 0.0)
        out.append(float(s))
    return out


def score_equal_sleeves(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Equal contribution.

    weighted_sleeves: mean of component/weight fractions on enabled sleeves.
    rank_primary / raw_score_primary: within-date z-score mean of feature_keys().
    """
    if policy.score_kind in ("rank_primary", "raw_score_primary"):
        return score_feature_equal_z(rows, policy)

    keys = enabled_keys(policy)
    weights = {c.key: c.weight for c in policy.enabled_components()}
    out: list[float] = []
    for r in rows:
        fracs = []
        for k in keys:
            w = weights[k] or 1.0
            fracs.append(r.components.get(k, 0.0) / w)
        out.append(float(np.mean(fracs)) if fracs else 0.0)
    return out


def score_feature_equal_z(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
) -> list[float]:
    """Within-date z-score mean of policy.feature_keys() — no leakage across dates."""
    keys = list(policy.feature_keys())
    if not keys:
        return [0.0] * len(rows)

    by_date: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_date[r.date].append(i)

    out = [0.0] * len(rows)
    for _date, idxs in by_date.items():
        mat = np.array(
            [[rows[i].components.get(k, 0.0) for k in keys] for i in idxs],
            dtype=float,
        )
        if mat.size == 0:
            continue
        mu = mat.mean(axis=0)
        sd = mat.std(axis=0)
        sd = np.where(sd < 1e-12, 1.0, sd)
        z = (mat - mu) / sd
        means = z.mean(axis=1)
        for j, i in enumerate(idxs):
            out[i] = float(means[j])
    return out


def score_ridge_reweight(
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    primary_horizon: int,
) -> tuple[list[float], dict[str, float]]:
    """Fit Ridge on train components → excess@H; predict test. Returns scores + coef map."""
    if policy.score_kind in ("rank_primary", "raw_score_primary"):
        keys = list(policy.feature_keys())
    else:
        keys = enabled_keys(policy)
    if not keys or len(train) < len(keys) + 2:
        return [0.0] * len(test), {k: 0.0 for k in keys}

    X_tr = np.array([[r.components.get(k, 0.0) for k in keys] for r in train], dtype=float)
    y_tr = np.array(
        [r.excess.get(primary_horizon, float("nan")) for r in train],
        dtype=float,
    )
    X_te = np.array([[r.components.get(k, 0.0) for k in keys] for r in test], dtype=float)

    m = np.isfinite(y_tr)
    if int(m.sum()) < len(keys) + 2 or float(np.std(y_tr[m])) < 1e-12:
        return [0.0] * len(test), {k: 0.0 for k in keys}

    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_tr[m])
    model = Ridge(alpha=1.0, random_state=42)
    model.fit(Xs, y_tr[m])
    pred = model.predict(scaler.transform(X_te))
    coefs = {
        k: float(c) for k, c in zip(keys, model.coef_, strict=True)
    }
    return pred.tolist(), coefs
