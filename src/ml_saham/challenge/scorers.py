"""Policy scorers for accum weight tournament."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.types import PolicySnapshot


def enabled_keys(policy: PolicySnapshot) -> list[str]:
    return [c.key for c in policy.enabled_components()]


def score_production(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Sum of component points (already in points space ≈ weight * quality)."""
    keys = enabled_keys(policy)
    return [float(sum(r.components.get(k, 0.0) for k in keys)) for r in rows]


def score_equal_sleeves(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Equal contribution: mean of normalized component fractions."""
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


def score_ridge_reweight(
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    primary_horizon: int,
) -> tuple[list[float], dict[str, float]]:
    """Fit Ridge on train components → excess@H; predict test. Returns scores + coef map."""
    keys = enabled_keys(policy)
    if len(train) < len(keys) + 2:
        return [0.0] * len(test), {k: 0.0 for k in keys}

    X_tr = np.array([[r.components.get(k, 0.0) for k in keys] for r in train], dtype=float)
    y_tr = np.array([r.excess[primary_horizon] for r in train], dtype=float)
    X_te = np.array([[r.components.get(k, 0.0) for k in keys] for r in test], dtype=float)

    # constant columns → ridge still ok
    if float(np.std(y_tr)) < 1e-12:
        return [0.0] * len(test), {k: 0.0 for k in keys}

    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_tr)
    model = Ridge(alpha=1.0, random_state=42)
    model.fit(Xs, y_tr)
    pred = model.predict(scaler.transform(X_te))
    coefs = {
        k: float(c) for k, c in zip(keys, model.coef_, strict=True)
    }
    return pred.tolist(), coefs
