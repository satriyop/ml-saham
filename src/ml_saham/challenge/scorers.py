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
    if policy.score_kind == "flag_penalty_adjusted":
        # raw_score − sum(weight_i) for each fired flag (component value 0/1)
        flag_keys = [c.key for c in policy.enabled_components() if c.key != "production_raw_score"]
        wmap = {c.key: c.weight for c in policy.enabled_components()}
        out: list[float] = []
        for r in rows:
            raw = float(r.components.get("production_raw_score", 0.0))
            pen = 0.0
            for k in flag_keys:
                if float(r.components.get(k, 0.0)) > 0.5:
                    pen += float(wmap.get(k, 0.0))
            out.append(raw - pen)
        return out
    if policy.score_kind == "classification_band":
        # Map raw score through strong/moderate floors → 100 / 50 / 0
        strong = 70.0
        moderate = 45.0
        for c in policy.components:
            if c.key == "strong_min":
                strong = float(c.weight)
            elif c.key == "moderate_min":
                moderate = float(c.weight)
        out = []
        for r in rows:
            raw = float(r.components.get("production_raw_score", 0.0))
            if raw >= strong:
                out.append(100.0)
            elif raw >= moderate:
                out.append(50.0)
            else:
                out.append(0.0)
        return out
    if policy.score_kind == "gate_block":
        # 1.0 = allowed (open), 0.0 = blocked by any enabled gate
        keys = enabled_keys(policy)
        out: list[float] = []
        for r in rows:
            blocked = any(float(r.components.get(k, 0.0)) > 0.0 for k in keys)
            out.append(0.0 if blocked else 1.0)
        return out
    if policy.score_kind == "evidence_group_weights":
        return score_evidence_group_weights(rows, policy)
    keys = enabled_keys(policy)
    return [float(sum(r.components.get(k, 0.0) for k in keys)) for r in rows]


def score_evidence_group_weights(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    weight_override: dict[str, float] | None = None,
    drop_key: str | None = None,
) -> list[float]:
    """Weighted mean of group scores; renormalize over enabled weights > 0.

    Mirrors production: missing groups drop out of the weight sum (not zero-filled).
    Group values are expected on a ~0–100 score scale.
    """
    wmap = dict(weight_override) if weight_override is not None else {
        c.key: float(c.weight) for c in policy.enabled_components()
    }
    if drop_key is not None:
        wmap = {k: (0.0 if k == drop_key else v) for k, v in wmap.items()}
    out: list[float] = []
    for r in rows:
        num = 0.0
        den = 0.0
        for k, w in wmap.items():
            if w <= 0:
                continue
            if k not in r.components:
                continue
            v = float(r.components[k])
            # treat pure missing zeros only if key absent — present 0 is real
            num += w * v
            den += w
        out.append(float(num / den) if den > 0 else 0.0)
    return out


def score_evidence_equal_groups(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
) -> list[float]:
    """Equal weight on every enabled group key that is present on the row."""
    keys = enabled_keys(policy)
    equal = {k: 1.0 for k in keys}
    return score_evidence_group_weights(rows, policy, weight_override=equal)


def score_flags_off(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Challenger: ignore flag penalties — raw_score only."""
    del policy
    return [float(r.components.get("production_raw_score", 0.0)) for r in rows]


def score_classification_shift(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    strong_delta: float = 5.0,
    moderate_delta: float = 5.0,
) -> list[float]:
    """Challenger: shift STRONG/MODERATE floors (default +5 / +5)."""
    strong = 70.0
    moderate = 45.0
    for c in policy.components:
        if c.key == "strong_min":
            strong = float(c.weight)
        elif c.key == "moderate_min":
            moderate = float(c.weight)
    strong += strong_delta
    moderate += moderate_delta
    out: list[float] = []
    for r in rows:
        raw = float(r.components.get("production_raw_score", 0.0))
        if raw >= strong:
            out.append(100.0)
        elif raw >= moderate:
            out.append(50.0)
        else:
            out.append(0.0)
    return out


def score_gate_off(rows: Sequence[PanelRow], policy: PolicySnapshot) -> list[float]:
    """Challenger: never block — all names allowed (1.0)."""
    del policy
    return [1.0] * len(rows)


def score_gate_off_named(
    rows: Sequence[PanelRow],
    policy: PolicySnapshot,
    gate_key: str,
) -> list[float]:
    """Challenger: disable one gate; other enabled gates still block."""
    keys = [k for k in enabled_keys(policy) if k != gate_key]
    out: list[float] = []
    for r in rows:
        blocked = any(float(r.components.get(k, 0.0)) > 0.0 for k in keys)
        out.append(0.0 if blocked else 1.0)
    return out


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
    evidence_group_weights: equal group weights (renormalized).
    """
    if policy.score_kind == "evidence_group_weights":
        return score_evidence_equal_groups(rows, policy)
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
