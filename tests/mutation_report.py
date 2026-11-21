#!/usr/bin/env python3
"""Print the validator's detection rate over the known violations in tests/mutations.py.

Usage: python3 -B tests/mutation_report.py [--min-rate 1.0]   (exit 1 when the rate is below --min-rate)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutations  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rate", type=float, default=0.0, help="Fail when caught/total is below this (0..1).")
    args = ap.parse_args()
    base = mutations.baseline()
    if base:
        print("golden example is not clean:", base)
        return 1
    caught = 0
    for name, (desc, _, _) in mutations.MUTATIONS.items():
        msgs = mutations.run_mutation(name)
        hit = mutations.caught(name, msgs)
        caught += hit
        print(f"{name}: {'CAUGHT' if hit else 'MISSED'}  {desc}")
    total = len(mutations.MUTATIONS)
    print(f"detection: {caught}/{total}")
    return 0 if caught / total >= args.min_rate else 1


if __name__ == "__main__":
    sys.exit(main())
