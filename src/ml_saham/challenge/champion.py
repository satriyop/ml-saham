"""Challenge champion track: learned scorers that try to beat production.

Purpose (distinct from tune): find a better *score rule* under the same
protocol. Production remains baseline; no auto-promote.

Train only on fold train; predict fold test. Fit never uses test labels.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ml_saham.challenge.panel import PanelRow
from ml_saham.challenge.scorers import enabled_keys
from ml_saham.challenge.types import PolicySnapshot

# Against ids reserved for champion track
CHAMPION_AGAINST_IDS: frozenset[str] = frozenset(
    {
        "lgbm_reweight",
        "lightgbm_reweight",
        "elastic_net_reweight",
        "enet_reweight",
    }
)

# Minimum train rows after filtering finite labels (beyond feature count)
_MIN_TRAIN_ABS = 25


def is_champion_against(against: str) -> bool:
    a = against.strip().lower().replace("-", "_")
    return a in CHAMPION_AGAINST_IDS


def normalize_champion_id(against: str) -> str:
    a = against.strip().lower().replace("-", "_")
    if a in ("lightgbm_reweight", "lgbm"):
        return "lgbm_reweight"
    if a in ("enet_reweight", "elasticnet_reweight"):
        return "elastic_net_reweight"
    return a


def feature_keys_for_learned(policy: PolicySnapshot) -> list[str]:
    """Component / feature keys used as the X matrix for learned champions."""
    if policy.score_kind in ("rank_primary", "raw_score_primary"):
        keys = list(policy.feature_keys())
    else:
        keys = enabled_keys(policy)
    return keys


def _xy(
    rows: Sequence[PanelRow],
    keys: list[str],
    primary_horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return X, y, finite_mask (row-aligned to input rows)."""
    X = np.array([[r.components.get(k, 0.0) for k in keys] for r in rows], dtype=float)
    y = np.array(
        [r.excess.get(primary_horizon, float("nan")) for r in rows],
        dtype=float,
    )
    m = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    return X, y, m


def score_lgbm_reweight(
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    primary_horizon: int,
) -> tuple[list[float] | None, dict[str, float], str | None]:
    """Fit LightGBM on train components → excess@H; predict test.

    Returns (scores | None, feature_importance-ish map, error_or_None).
    None scores + error ⇒ caller should BLOCKED_* (honest).
    """
    keys = feature_keys_for_learned(policy)
    if not keys:
        return None, {}, "champion lgbm_reweight: no feature keys on policy"

    try:
        from lightgbm import LGBMRegressor
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None, {}, (
            "champion lgbm_reweight requires lightgbm+sklearn "
            "(pip install -e '.[ml]')"
        )

    X_tr, y_tr, m_tr = _xy(train, keys, primary_horizon)
    n_ok = int(m_tr.sum())
    min_need = max(_MIN_TRAIN_ABS, len(keys) + 5)
    if n_ok < min_need:
        return None, {}, (
            f"champion lgbm_reweight: train n_ok={n_ok} < min={min_need} "
            f"(n_train={len(train)}, n_features={len(keys)})"
        )
    if float(np.std(y_tr[m_tr])) < 1e-12:
        return None, {}, "champion lgbm_reweight: constant train labels (no variance)"

    X_te, _y_te, _m_te = _xy(test, keys, primary_horizon)
    if len(test) == 0:
        return None, {}, "champion lgbm_reweight: empty test fold"

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_tr[m_tr])
    model = LGBMRegressor(
        n_estimators=40,
        max_depth=3,
        learning_rate=0.05,
        min_child_samples=max(5, n_ok // 20),
        random_state=42,
        verbosity=-1,
    )
    model.fit(Xs, y_tr[m_tr])
    pred = np.asarray(model.predict(scaler.transform(X_te)), dtype=float)
    if float(np.std(pred)) < 1e-12:
        return None, {}, (
            "champion lgbm_reweight: constant predictions (degenerate fit)"
        )
    # importance as pseudo-coefs for report
    imp = getattr(model, "feature_importances_", None)
    meta: dict[str, float] = {}
    if imp is not None and len(imp) == len(keys):
        total = float(np.sum(imp)) or 1.0
        meta = {k: float(v) / total for k, v in zip(keys, imp, strict=True)}
    else:
        meta = {k: 0.0 for k in keys}
    meta["_n_train_ok"] = float(n_ok)
    meta["_n_test"] = float(len(test))
    return [float(x) for x in pred], meta, None


def score_elastic_net_reweight(
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    primary_horizon: int,
) -> tuple[list[float] | None, dict[str, float], str | None]:
    """Fit ElasticNet on train components → excess@H; predict test."""
    keys = feature_keys_for_learned(policy)
    if not keys:
        return None, {}, "champion elastic_net_reweight: no feature keys on policy"

    try:
        from sklearn.linear_model import ElasticNet
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None, {}, (
            "champion elastic_net_reweight requires sklearn "
            "(pip install -e '.[ml]')"
        )

    X_tr, y_tr, m_tr = _xy(train, keys, primary_horizon)
    n_ok = int(m_tr.sum())
    min_need = max(_MIN_TRAIN_ABS, len(keys) + 5)
    if n_ok < min_need:
        return None, {}, (
            f"champion elastic_net_reweight: train n_ok={n_ok} < min={min_need}"
        )
    if float(np.std(y_tr[m_tr])) < 1e-12:
        return None, {}, "champion elastic_net_reweight: constant train labels"

    X_te, _y_te, _m_te = _xy(test, keys, primary_horizon)
    if len(test) == 0:
        return None, {}, "champion elastic_net_reweight: empty test fold"

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X_tr[m_tr])
    # Mild regularization so coefs are not all shrunk to zero on small panels
    model = ElasticNet(alpha=0.01, l1_ratio=0.15, random_state=42, max_iter=10000)
    model.fit(Xs, y_tr[m_tr])
    pred = np.asarray(model.predict(scaler.transform(X_te)), dtype=float)
    if float(np.std(pred)) < 1e-12 or float(np.max(np.abs(model.coef_))) < 1e-12:
        return None, {}, (
            "champion elastic_net_reweight: constant/zero-coef predictions "
            "(degenerate fit — try lgbm_reweight or more train data)"
        )
    meta = {k: float(c) for k, c in zip(keys, model.coef_, strict=True)}
    meta["_n_train_ok"] = float(n_ok)
    meta["_n_test"] = float(len(test))
    return [float(x) for x in pred], meta, None


def score_champion(
    against: str,
    train: Sequence[PanelRow],
    test: Sequence[PanelRow],
    policy: PolicySnapshot,
    *,
    primary_horizon: int,
) -> tuple[list[float] | None, dict[str, float], str | None]:
    """Dispatch champion against id → scores."""
    cid = normalize_champion_id(against)
    if cid == "lgbm_reweight":
        return score_lgbm_reweight(
            train, test, policy, primary_horizon=primary_horizon
        )
    if cid == "elastic_net_reweight":
        return score_elastic_net_reweight(
            train, test, policy, primary_horizon=primary_horizon
        )
    return None, {}, f"unknown champion against {against!r}"
