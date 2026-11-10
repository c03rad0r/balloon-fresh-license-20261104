#!/usr/bin/env python3
"""Tombstone for unsafe, unmerged 053daa96 generator; intentionally emits no PCB."""
import sys


def main():
    print("QUARANTINED: 053daa96 pressure-rig scaffold is not an electrical design. "
          "See docs/prestretch/PRESSURE-RIG-ELECTRICAL-BLOCKERS.md. No PCB generated.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
