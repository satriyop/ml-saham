#!/usr/bin/env python3
"""Run the outcome-independent ML-OOS-02 synthetic calibration study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_calibration import (  # noqa: E402
    default_calibration_methods,
    default_calibration_scenarios,
    format_calibration_report,
    run_calibration_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-count",
        type=int,
        action="append",
        dest="session_counts",
        help="Total synthetic sessions; repeat for a grid (default: 84,120,180)",
    )
    parser.add_argument("--holdout-sessions", type=int, default=20)
    parser.add_argument("--n-folds", type=int, default=3)
    parser.add_argument("--embargo-sessions", type=int, default=20)
    parser.add_argument("--replications", type=int, default=100)
    parser.add_argument("--bootstrap-resamples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scenarios = default_calibration_scenarios(
        session_counts=tuple(args.session_counts or (84, 120, 180)),
        holdout_sessions=args.holdout_sessions,
    )
    methods = default_calibration_methods(n_resamples=args.bootstrap_resamples)
    study = run_calibration_study(
        scenarios=scenarios,
        methods=methods,
        seed=args.seed,
        n_replications=args.replications,
        n_folds=args.n_folds,
        embargo_sessions=args.embargo_sessions,
    )
    if args.json:
        print(json.dumps(study.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_calibration_report(study))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
