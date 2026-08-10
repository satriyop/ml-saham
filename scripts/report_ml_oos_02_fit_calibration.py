#!/usr/bin/env python3
"""Run synthetic calibration through shipped learned fit/predict pipelines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_calibration import (  # noqa: E402
    default_calibration_methods,
)
from ml_saham.challenge.policy_confirmation_fit_calibration import (  # noqa: E402
    default_fit_calibration_scenarios,
    format_fit_calibration_report,
    run_fit_calibration_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-count", type=int, action="append")
    parser.add_argument("--holdout-sessions", type=int, default=20)
    parser.add_argument("--replications", type=int, default=30)
    parser.add_argument("--bootstrap-resamples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    scenarios = default_fit_calibration_scenarios(
        session_counts=tuple(args.session_count or (84, 120, 180)),
        holdout_sessions=args.holdout_sessions,
    )
    methods = default_calibration_methods(n_resamples=args.bootstrap_resamples)
    study = run_fit_calibration_study(
        scenarios=scenarios,
        methods=methods,
        seed=args.seed,
        n_replications=args.replications,
    )
    if args.json:
        print(json.dumps(study.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_fit_calibration_report(study))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
