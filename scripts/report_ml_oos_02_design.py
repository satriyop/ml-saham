#!/usr/bin/env python3
"""Print the ML-OOS-02 design-study report (non-authoritative).

Does not write Protocol thresholds or register confirmation contracts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_design import (  # noqa: E402
    build_ml_oos_02_design_study,
    format_design_study_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-folds", type=int, default=3)
    parser.add_argument("--embargo-sessions", type=int, default=20)
    parser.add_argument("--min-folds-for-verdict", type=int, default=2)
    parser.add_argument("--n-sessions-total", type=int, default=120)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable study bundle JSON",
    )
    args = parser.parse_args()
    bundle = build_ml_oos_02_design_study(
        n_folds=args.n_folds,
        embargo_sessions=args.embargo_sessions,
        min_folds_for_verdict=args.min_folds_for_verdict,
        n_sessions_total_for_holdout=args.n_sessions_total,
    )
    if args.json:
        print(json.dumps(bundle.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_design_study_report(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
