"""Ch.21 Seasonality drift — calendar month anomalies using default models."""

from __future__ import annotations

from collections import defaultdict
import math

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, load_candles
from ml_saham.data.phase2_read import load_seasonality

META = get_meta("seasonality-drift")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Apakah anomali musiman (misal: 'April dividend rally', 'December Santa rally')",
        "  secara statistik signifikan, atau sekadar overfit histori?",
        "",
        "Opsi pendekatan",
        "  1) Default: Model Prophet / NeuralProphet untuk dekomposisi sinyal musiman (yearly seasonality)",
        "  2) Baseline (compare): Rata-rata sederhana return berdasarkan bulan (naive month-of-year average)",
        "",
        "Caveat",
        "  • Anomali kalender sering hilang setelah dipublikasikan",
        "  • Sample size bulanan relatif terbatas",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
        f"Bandingkan: ml-saham compare {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: Menggunakan Prophet untuk memisahkan komponen musiman pada return harian.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        import pandas as pd
        from prophet import Prophet
        import logging
        logging.getLogger("cmdstanpy").disabled = True
    except ImportError as exc:
        raise ChapterError("Butuh pandas & prophet: pip install pandas prophet") from exc

    with connect(ctx.db_path) as conn:
        rows = load_candles(conn, ctx.universe)

    if not rows:
        raise ChapterDataError("Candles kosong.", hint="ml-saham fetch market")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    df["return"] = df.groupby("ticker")["close"].pct_change() * 100
    df = df.dropna(subset=["return"])

    ticker = ctx.universe[0] if ctx.universe else df["ticker"].iloc[0]
    df_t = df[df["ticker"] == ticker].copy()

    if len(df_t) < 252:
        raise ChapterDataError(f"Data candles {ticker} terlalu sedikit.")

    df_t = df_t.rename(columns={"date": "ds", "return": "y"})

    # Fit Prophet
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    model.fit(df_t[["ds", "y"]])

    # Extract seasonal component for each month
    future = pd.DataFrame({'ds': pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')})
    forecast = model.predict(future)
    
    forecast['month'] = forecast['ds'].dt.month
    if 'yearly' in forecast.columns:
        monthly_seasonality = forecast.groupby('month')['yearly'].mean().to_dict()
    else:
        # Fallback if yearly component is somehow named differently
        monthly_seasonality = forecast.groupby('month')['yhat'].mean().to_dict()

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_stats = []
    for m in range(1, 13):
        monthly_stats.append((m, month_names[m-1], monthly_seasonality.get(m, 0.0)))
        
    monthly_stats.sort(key=lambda x: -x[2])

    lines = [
        f"Ticker: {ticker} (n={len(df_t)})",
        "Default (Prophet) Yearly Seasonality Component:",
        "",
        "Ranking rata-rata efek musiman bulanan:"
    ]
    for m, name, effect in monthly_stats:
        lines.append(f"  {name:<4} (Bulan {m:2d})  seasonality_effect={effect:+.3f}%")

    metrics = {
        "n_records": len(df_t),
        "ticker": ticker,
    }

    return DemoResult(
        title="Seasonality drift · Default Prophet Demo",
        lines=lines,
        metrics=metrics,
        model="prophet_seasonality",
        summary_md=f"# Seasonality drift\n\nProphet model fitted on {ticker}.\n",
        scoreboard=False,
        scoreboard_kind="none",
    )


def run_compare(ctx: ChapterContext) -> DemoResult:
    try:
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import Ridge
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        from sklearn.preprocessing import OneHotEncoder
    except ImportError as exc:
        raise ChapterError("Butuh pandas & scikit-learn: pip install -e .") from exc

    with connect(ctx.db_path) as conn:
        uni = ctx.universe or []
        rows = load_candles(conn, uni if uni else None)

    if not rows:
        raise ChapterDataError("Candles kosong.")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    df["return"] = df.groupby("ticker")["close"].pct_change() * 100
    df = df.dropna(subset=["return"])

    ticker = uni[0] if uni else str(df["ticker"].iloc[0])
    df_t = df[df["ticker"] == ticker].copy()
    if len(df_t) < 40:
        raise ChapterDataError(f"Data candles {ticker} terlalu sedikit untuk seasonality compare.")

    test_n = min(20, max(8, len(df_t) // 4))
    split_idx = len(df_t) - test_n
    train_df = df_t.iloc[:split_idx].copy()
    test_df = df_t.iloc[split_idx:].copy()
    train_df["month"] = train_df["date"].dt.month
    test_df["month"] = test_df["date"].dt.month

    monthly_avg = train_df.groupby("month")["return"].mean().to_dict()
    baseline_preds = test_df["month"].map(monthly_avg).fillna(0).values
    actual = test_df["return"].values

    against_name = "Ridge month dummies"
    model_tag = "ridge_month_vs_naive"
    try:
        enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
        X_train = enc.fit_transform(train_df[["month"]])
        X_test = enc.transform(test_df[["month"]])
        ridge = Ridge(alpha=1.0, random_state=42)
        ridge.fit(X_train, train_df["return"].values)
        against_preds = ridge.predict(X_test)
    except Exception:
        against_preds = baseline_preds
        against_name = "fallback=baseline"
        model_tag = "seasonality_fallback"

    # Optional Prophet when installed and history is long enough
    if len(df_t) >= 200:
        try:
            import logging

            from prophet import Prophet

            logging.getLogger("cmdstanpy").disabled = True
            train_p = train_df[["date", "return"]].rename(columns={"date": "ds", "return": "y"})
            test_p = test_df[["date"]].rename(columns={"date": "ds"})
            model = Prophet(
                yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False
            )
            model.fit(train_p)
            against_preds = model.predict(test_p)["yhat"].values
            against_name = "Prophet"
            model_tag = "prophet_vs_naive"
        except Exception:
            pass

    against_rmse = float(np.sqrt(mean_squared_error(actual, against_preds)))
    base_rmse = float(np.sqrt(mean_squared_error(actual, baseline_preds)))
    against_mae = float(mean_absolute_error(actual, against_preds))
    base_mae = float(mean_absolute_error(actual, baseline_preds))

    lines = [
        f"Ticker: {ticker} (test n={test_n})",
        "",
        f"Default ({against_name}):",
        f"  RMSE: {against_rmse:.6f}",
        f"  MAE:  {against_mae:.6f}",
        "",
        "Baseline (Naive Month Avg):",
        f"  RMSE: {base_rmse:.6f}",
        f"  MAE:  {base_mae:.6f}",
        "",
        f"Winner (RMSE): {'Default' if against_rmse < base_rmse else 'Baseline'}",
    ]

    metrics = {
        "against_rmse": against_rmse,
        "base_rmse": base_rmse,
        "against_mae": against_mae,
        "base_mae": base_mae,
        "against_model": against_name,
    }

    return DemoResult(
        title="Compare Default vs Baseline · Seasonality Drift",
        lines=lines,
        metrics=metrics,
        model=model_tag,
        summary_md=(
            f"# Compare Seasonality\n\nDefault ({against_name}) RMSE: {against_rmse:.4f} "
            f"vs Baseline RMSE: {base_rmse:.4f}"
        ),
        scoreboard=False,
        scoreboard_kind="none",
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="seasonality_cache di ai-saham",
        bring_back="Prophet seasonality forecast & OOS comparison",
    )
