"""Ch.15 Corp events — event study around ex_date."""

from __future__ import annotations

import random
from collections import Counter, defaultdict

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_squared_error
    from sklearn.dummy import DummyRegressor
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ml_saham.chapters.errors import ChapterDataError
from ml_saham.chapters.panel import resolve_universe
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult, CompareResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.data.phase2_read import load_corp_actions

META = get_meta("corp-events")

def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Dividen, stock split, rights — peristiwa korporasi mengubah return path.",
        "",
        "Opsi algoritma",
        "  Default: Event-driven Random Forest/XGBoost",
        "    Model membaca tipe event dan return historis untuk memprediksi reaksi CAR.",
        "  Baseline (compare): Mean-reversion dummy",
        "    Asumsi mean reversion sederhana atau baseline konstan vs default.",
        "",
        "Caveat",
        "  • ex_date adjustment bisa belum sempurna di harga",
        "  • Sample kecil per tipe event",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Bandingkan: ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: load_corp_actions dari corp_action_cache.")
    return "\n".join(lines)

def _fwd_around(
    by_t: dict[str, list[tuple[str, float]]], ticker: str, ex_date: str, horizon: int = 5
) -> float | None:
    series = by_t.get(ticker)
    if not series:
        return None
    series = sorted(series, key=lambda x: x[0])
    dates = [d for d, _ in series]
    if ex_date not in dates:
        idxs = [i for i, d in enumerate(dates) if d <= ex_date]
        if not idxs:
            return None
        i0 = idxs[-1]
    else:
        i0 = dates.index(ex_date)
    i1 = i0 + horizon
    if i1 >= len(series):
        return None
    c0, c1 = series[i0][1], series[i1][1]
    if c0 == 0:
        return None
    return (c1 / c0) - 1.0

def _build_dataset(ctx: ChapterContext):
    with connect(ctx.db_path) as conn:
        uni = ctx.universe or resolve_universe(conn, limit=50)
        events = load_corp_actions(conn, uni)
        if not events:
            raise ChapterDataError(
                "corp_action_cache / corporate_action_events kosong.",
                hint="ml-saham doctor",
            )
        candles = load_candles(conn, uni)

    by_t: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in candles:
        by_t[row["ticker"]].append((row["date"], float(row["close"])))

    scored: list[dict] = []
    type_counts = Counter(str(e.get("event_type", "unknown")) for e in events)
    
    for e in events:
        t = e.get("ticker")
        ex = e.get("ex_date")
        etype = str(e.get("event_type", "unknown"))
        if not t or not ex:
            continue
        fwd = _fwd_around(by_t, t, ex, horizon=5)
        ihsg_fwd = _fwd_around(by_t, "IHSG", ex, horizon=5)
        if fwd is None:
            continue
        car = fwd - (ihsg_fwd if ihsg_fwd is not None else 0.0)
        
        # Simple feature: event type encoding + month of ex_date
        # Just mapping event_type to a hash integer for simplicity in demo
        feat_etype = hash(etype) % 100
        feat_month = int(ex[5:7]) if len(ex) >= 7 else 0
        features = [feat_etype, feat_month]
        
        scored.append({
            "ticker": t,
            "event_type": etype,
            "ex_date": ex,
            "fwd": fwd,
            "car": car,
            "features": features
        })

    if not scored:
        raise ChapterDataError("Tidak ada event dengan forward return valid.")
        
    return scored, type_counts, len(events), len(uni)

def run_demo(ctx: ChapterContext) -> DemoResult:
    scored, type_counts, n_events, n_uni = _build_dataset(ctx)
    
    lines = [
        f"events={n_events}  with_fwd={len(scored)}  universe={n_uni}",
        "",
        "Count by event_type:",
    ]
    for et, cnt in type_counts.most_common(8):
        lines.append(f"  {et}: {cnt}")
    lines.append("")

    if HAS_SKLEARN and len(scored) > 5:
        X = np.array([s["features"] for s in scored])
        y = np.array([s["car"] for s in scored])
        
        # Split train/test (80/20)
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        
        # We predict for all to rank them
        all_preds = model.predict(X)
        for i, s in enumerate(scored):
            s["score"] = all_preds[i]
            
        test_mse = mean_squared_error(y_test, preds)
        lines.append(f"Default: RandomForestRegressor (Test MSE={test_mse:.6f})")
        model_name = "default_rf"
    else:
        lines.append("Default: Sklearn not available, using dummy scoring.")
        for s in scored:
            s["score"] = s["car"] + random.uniform(-0.01, 0.01)
        model_name = "fallback"

    overall_car = sum(s["car"] for s in scored) / len(scored)
    
    top = sorted(scored, key=lambda s: s["score"], reverse=True)[:10]
    metrics = {
        "n_events": n_events,
        "n_with_fwd": len(scored),
        "type_counts": dict(type_counts),
        "mean_car_overall": overall_car,
    }
    
    return DemoResult(
        title="Corp events · Default Random Forest",
        lines=lines,
        metrics=metrics,
        model=model_name,
        summary_md=f"# Corp events (default)\n\n{len(scored)} events evaluated.\n",
        scoreboard=True,
        top_names=top,
    )

def run_compare(ctx: ChapterContext) -> CompareResult:
    scored, _, _, _ = _build_dataset(ctx)
    if not HAS_SKLEARN or len(scored) < 10:
        raise ChapterDataError("Sklearn required and at least 10 events needed for compare.")
        
    X = np.array([s["features"] for s in scored])
    y = np.array([s["car"] for s in scored])
    
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # default
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    rf_mse = mean_squared_error(y_test, rf_preds)
    
    # Baseline: Mean-reversion dummy (predicting mean or constant)
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    dummy_preds = dummy.predict(X_test)
    dummy_mse = mean_squared_error(y_test, dummy_preds)
    
    lines = [
        "Comparing Models for Corp Events (CAR prediction):",
        "",
        f"1. Default (RandomForest): Test MSE = {rf_mse:.6f}",
        f"2. Baseline (Mean Dummy): Test MSE = {dummy_mse:.6f}",
        "",
        "RandomForest utilizes event features to predict abnormal returns,",
        "while Baseline merely predicts the historical mean.",
    ]
    
    metrics = {
        "against_mse": float(rf_mse),
        "baseline_mse": float(dummy_mse),
        "win": "Default" if rf_mse < dummy_mse else "Baseline",
    }
    
    return CompareResult(
        title="Default vs Mean-reversion dummy",
        lines=lines,
        metrics=metrics,
        winner=metrics["win"],
        summary_md=f"# Compare Corp Events\n\nDefault MSE: {rf_mse:.6f}\nBaseline MSE: {dummy_mse:.6f}\n",
    )

