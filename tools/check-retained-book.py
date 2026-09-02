#!/usr/bin/env python3
"""Verify data/encounters.json by deterministic clean retained-book regeneration."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from retained_wiki import AuditError, verify_clean_book_regeneration

try:
    verify_clean_book_regeneration(ROOT)
except AuditError as exc:
    print(f"retained-book check failed: {exc}", file=sys.stderr)
    raise SystemExit(1)
print("verified byte-identical data/encounters.json by clean retained-book regeneration")
