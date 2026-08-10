#!/usr/bin/env python3
"""Report the non-authoritative ML-OOS-02 target-contract vet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_saham.challenge.policy_confirmation_target_vet import (  # noqa: E402
    format_target_contract_vet,
    vet_current_policy_confirmation_target,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = vet_current_policy_confirmation_target()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_target_contract_vet(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
