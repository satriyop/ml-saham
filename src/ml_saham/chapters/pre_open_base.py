"""Shared logic for pre-open evaluation modes."""

from __future__ import annotations

import json
import sqlite3
import numpy as np

from ml_saham.chapters.errors import ChapterDataError
from ml_saham.data.aisaham_read import connect
from ml_saham.eval.metrics import rank_ic


def fetch_and_evaluate_pre_open(
    db_path: str,
    feature_keys: list[str],
    mode_name: str,
) -> dict:
    from ml_saham.data.observation_cohort import curriculum_payload_rows

    with connect(db_path) as conn:
        # 1. Fetch pre-open observations (single compatibility cohort)
        obs_rows, _ = curriculum_payload_rows(
            conn,
            "PRE_OPEN_AUCTION_DIRECTION",
            limit=2000,
            include_captured_at=True,
        )

        if not obs_rows:
            raise ChapterDataError("learning_observations untuk PRE_OPEN kosong.")
            
        # 2. Extract Data
        parsed_data = []
        for row in obs_rows:
            try:
                payload = json.loads(row["decision_payload_json"])
                ticker = payload.get("ticker")
                date = payload.get("snapshot_date")
                if not ticker or not date:
                    continue
                
                # Baseline rank or score (fallback to raw_score)
                signal = payload.get("signal", {})
                baseline_score = float(signal.get("raw_score", 0.0))
                
                # Extract Candidate / Signal Factors
                cand = payload.get("candidate", {})
                factors = signal.get("factors", {})
                
                # Flatten the relevant dict
                flat_features = {}
                for k, v in cand.items():
                    if isinstance(v, (int, float, bool)):
                        flat_features[k] = float(v)
                for k, v in factors.items():
                    if isinstance(v, (int, float, bool)):
                        flat_features[k] = float(v)
                        
                parsed_data.append({
                    "ticker": ticker,
                    "date": date,
                    "baseline_score": baseline_score,
                    "features": flat_features
                })
            except Exception:
                continue

        if not parsed_data:
            raise ChapterDataError("Gagal parsing JSON payload untuk pre-open.")
            
        # 3. Query Candles for Actual Intraday Return
        # Build IN clauses
        dates_tickers = [(d["ticker"], d["date"]) for d in parsed_data]
        placeholders = ", ".join(["(?, ?)"] * len(dates_tickers))
        params = []
        for t, d in dates_tickers:
            params.extend([t, d])
            
        # We need to make sure sqlite version supports IN (tuple). Some don't.
        # Fallback: just fetch all candles for the distinct dates
        distinct_dates = list(set(d["date"] for d in parsed_data))
        placeholders = ", ".join(["?"] * len(distinct_dates))
        
        candle_cursor = conn.execute(
            f"SELECT ticker, date, open, close FROM candles WHERE date IN ({placeholders})",
            distinct_dates
        )
        candle_rows = candle_cursor.fetchall()
        
        # Build map (ticker, date) -> return
        returns_map = {}
        for r in candle_rows:
            try:
                op = float(r["open"])
                cl = float(r["close"])
                if op > 0:
                    returns_map[(r["ticker"], r["date"])] = (cl - op) / op
            except (ValueError, TypeError):
                continue
                
        # 4. Finalize Dataset
        X_list = []
        y_list = []
        b_list = []
        meta = []
        
        for d in parsed_data:
            ret = returns_map.get((d["ticker"], d["date"]))
            if ret is None:
                continue  # Skip if no candle (e.g. suspended or missing data)
                
            # Extract features requested for this mode
            feat_vec = []
            for k in feature_keys:
                feat_vec.append(d["features"].get(k, 0.0))
                
            X_list.append(feat_vec)
            y_list.append(ret)
            b_list.append(d["baseline_score"])
            meta.append({"ticker": d["ticker"], "date": d["date"]})
            
    if len(X_list) < 2:
        raise ChapterDataError(
            f"Hanya ditemukan {len(X_list)} sampel di learning_observations (butuh min 2). "
            "Sistem ai-saham Anda sepertinya baru merekam sedikit log PRE_OPEN_AUCTION_DIRECTION. "
            "Coba jalankan 'saham trade pre-open' pada hari bursa aktif untuk memperbanyak sampel!"
        )
        
    X_arr = np.array(X_list)
    y_arr = np.array(y_list)
    
    baseline_ic = rank_ic(b_list, y_list)
    
    # Train Default (XGBoost)
    try:
        from xgboost import XGBRegressor
        clf = XGBRegressor(n_estimators=10, max_depth=2, learning_rate=0.05, random_state=42)
        if len(set(y_list)) > 1:
            clf.fit(X_arr, y_arr)
            against_scores = clf.predict(X_arr)
            against_ic = rank_ic(against_scores.tolist(), y_list)
            
            importances = clf.feature_importances_
            if importances.sum() > 0:
                importances = (importances / importances.sum()) * 100
        else:
            against_ic = 0.0
            importances = np.zeros(len(feature_keys))
    except ImportError:
        try:
            # Fallback to LGBM if XGBoost is missing
            from lightgbm import LGBMRegressor
            clf = LGBMRegressor(n_estimators=50, max_depth=3, learning_rate=0.05, random_state=42)
            clf.fit(X_arr, y_arr)
            against_scores = clf.predict(X_arr)
            against_ic = rank_ic(against_scores.tolist(), y_list)
            importances = clf.feature_importances_
            if importances.sum() > 0:
                importances = (importances / importances.sum()) * 100
        except ImportError:
            against_ic = 0.0
            importances = np.zeros(len(feature_keys))

    return {
        "mode": mode_name,
        "n_samples": len(meta),
        "latest_date": meta[0]["date"] if meta else "UNKNOWN",
        "baseline_ic": baseline_ic,
        "against_ic": against_ic,
        "features": feature_keys,
        "importances": importances.tolist(),
    }
