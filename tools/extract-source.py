#!/usr/bin/env python3
"""Regenerate or verify the checked source-first world-model artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Running this file directly puts tools/ on sys.path, so the local package is
# importable without installation or PYTHONPATH changes.
from source_extractor.canonical import atomic_write
from source_extractor.dependencies import require_metadata_dependencies
from source_extractor.errors import SourceExtractionError
from source_extractor.input_gate import verify_inputs

_DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data/game-v0.111.0-source.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read exact v0.111.0 game files as bytes and derive canonical "
            "normalized monster identities/names, HP formulas/scaling, and encounter roster/pool facts. No game code is executed."
        )
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        required=True,
        help="explicit Slay the Spire 2 installation root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"artifact destination (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify byte equality with --output; do not replace it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_metadata_dependencies()
        # Import only after exact pinned dependency versions are confirmed.
        from source_extractor.extractor import build_artifact

        verified = verify_inputs(args.game_root)
        generated = build_artifact(verified)
        if args.check:
            try:
                existing = args.output.read_bytes()
            except OSError as exc:
                raise SourceExtractionError(
                    f"cannot read checked artifact {args.output}: {exc}"
                ) from exc
            if existing != generated:
                raise SourceExtractionError(
                    f"checked artifact differs: regenerate {args.output} without --check"
                )
            print(f"verified byte-identical artifact: {args.output}")
        else:
            atomic_write(args.output, generated)
            print(f"wrote {args.output} ({len(generated)} bytes)")
        return 0
    except SourceExtractionError as exc:
        print(f"source extraction failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # no traceback by default; keep failures actionable.
        print(
            f"source extraction failed unexpectedly: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
