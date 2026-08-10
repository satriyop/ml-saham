#!/usr/bin/env python3
"""Report live ACCUM cohort feasibility for ML-OOS-02, read-only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_feasibility import (  # noqa: E402
    DEFAULT_POLICY_ID,
    audit_accum_cohort_feasibility,
    format_feasibility_report,
)
from ml_saham.data.connection import resolve_db_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--policy-id", default=DEFAULT_POLICY_ID)
    parser.add_argument(
        "--compatibility-id",
        action="append",
        dest="compatibility_ids",
        help="Audit this exact ACCUM cohort; repeat for multiple separate cohorts",
    )
    parser.add_argument(
        "--holdout-sessions",
        nargs="+",
        type=int,
        default=[5, 10, 20, 40],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    audit = audit_accum_cohort_feasibility(
        resolve_db_path(args.db),
        policy_id=args.policy_id,
        compatibility_ids=args.compatibility_ids,
        holdout_candidates=args.holdout_sessions,
    )
    if args.json:
        print(json.dumps(audit.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_feasibility_report(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
