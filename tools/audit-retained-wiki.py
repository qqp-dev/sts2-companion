#!/usr/bin/env python3
"""Build or strictly verify the offline retained-wiki reconciliation inventory."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from retained_wiki import AuditError, DEFAULT_ARTIFACT, write_or_check

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/check the deterministic v0.111.0 retained-wiki origin inventory and P1b0/P1b1 final mappings; no network or game access."
    )
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_ARTIFACT))
    parser.add_argument("--check", action="store_true", help="require byte-identical checked artifact; never write")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        count, generated = write_or_check(args.root, args.output, check=args.check)
        verb = "verified byte-identical" if args.check else "wrote"
        print(f"{verb} {args.output} ({count} retained origins, {len(generated)} bytes)")
        return 0
    except AuditError as exc:
        print(f"retained-wiki reconciliation failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"retained-wiki reconciliation failed unexpectedly: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
