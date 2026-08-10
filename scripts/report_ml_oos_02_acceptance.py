#!/usr/bin/env python3
"""Run the non-authoritative ML-OOS-02 candidate acceptance study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_acceptance import (  # noqa: E402
    default_acceptance_methods,
    default_acceptance_scenarios,
    format_acceptance_report,
    run_acceptance_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-count",
        type=int,
        action="append",
        dest="session_counts",
        help="Total synthetic sessions; repeat for a grid (default: 120,180,252)",
    )
    parser.add_argument(
        "--higher-grid",
        action="store_true",
        help="Use the predeclared 360,504,756 session grid",
    )
    parser.add_argument(
        "--automatic-only",
        action="store_true",
        help="Evaluate only the automatic stationary-bootstrap candidate",
    )
    parser.add_argument("--holdout-sessions", type=int, default=20)
    parser.add_argument("--n-folds", type=int, default=3)
    parser.add_argument("--embargo-sessions", type=int, default=20)
    parser.add_argument(
        "--replications",
        type=int,
        default=100,
        help="Monte Carlo replications (quick default: 100; precision runs require more)",
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=100,
        help="Resamples per stationary-bootstrap interval (default: 100)",
    )
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.session_counts and args.higher_grid:
        parser.error("--session-count and --higher-grid are mutually exclusive")
    session_counts = tuple(
        args.session_counts or ((360, 504, 756) if args.higher_grid else (120, 180, 252))
    )
    scenarios = default_acceptance_scenarios(
        session_counts=session_counts,
        holdout_sessions=args.holdout_sessions,
    )
    methods = default_acceptance_methods(n_resamples=args.bootstrap_resamples)
    if args.automatic_only:
        methods = tuple(
            method
            for method in methods
            if method.method_kind == "stationary_bootstrap_percentile_auto"
        )
    study = run_acceptance_study(
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
        print(format_acceptance_report(study))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
