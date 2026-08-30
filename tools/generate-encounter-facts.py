#!/usr/bin/env python3
"""Generate or verify the checked compact C0 encounter projection."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from encounter_projection.builder import regenerate
from source_extractor.errors import SourceExtractionError

_REPO = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact encounter facts from exactly two checked data inputs; no game-root access.")
    parser.add_argument("--source", type=Path, default=_REPO / "data/game-v0.111.0-source.json")
    parser.add_argument("--legacy", type=Path, default=_REPO / "data/encounters.json")
    parser.add_argument("--output", type=Path, default=_REPO / "data/encounter-facts-v0.111.0.json")
    parser.add_argument("--check", action="store_true", help="require byte-identical checked output; never replace it")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generated = regenerate(args.source, args.legacy, args.output, check=args.check)
        verb = "verified byte-identical" if args.check else "wrote"
        print(f"{verb} {args.output} ({len(generated)} bytes)")
        return 0
    except SourceExtractionError as exc:
        print(f"encounter projection failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"encounter projection failed unexpectedly: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
