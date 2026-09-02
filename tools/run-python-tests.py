#!/usr/bin/env python3
"""Run the repository's independent Python unittest shards with strict aggregation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "test"
sys.path.insert(0, str(TEST_ROOT))
from test_encounter_projection import EncounterProjectionTests


def command(label: str, arguments: list[str], cwd: Path = ROOT) -> tuple[str, list[str], Path]:
    return label, [sys.executable, *arguments], cwd


def run(item: tuple[str, list[str], Path]) -> tuple[str, int, str]:
    label, arguments, cwd = item
    completed = subprocess.run(
        arguments, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    return label, completed.returncode, completed.stdout


methods = sorted(name for name in dir(EncounterProjectionTests) if name.startswith("test_"))
if len(methods) != 37:
    print(f"python test runner failed: expected 37 encounter projection tests, found {len(methods)}", file=sys.stderr)
    raise SystemExit(1)
shards = [methods[index::4] for index in range(4)]
commands = [
    command(
        f"encounter-projection-{index + 1}",
        ["-m", "unittest", *[f"test_encounter_projection.EncounterProjectionTests.{name}" for name in shard]],
        TEST_ROOT,
    )
    for index, shard in enumerate(shards)
]
commands.extend([
    command("retained-wiki-audit", ["test/test_retained_wiki_audit.py"]),
    command("source-tools", ["test/test_source_tools.py"]),
])

with ThreadPoolExecutor(max_workers=len(commands)) as executor:
    results = list(executor.map(run, commands))
failed = False
for label, returncode, output in results:
    print(f"--- {label} ---")
    print(output, end="" if output.endswith("\n") else "\n")
    if returncode:
        failed = True
if failed:
    raise SystemExit(1)
print(f"all Python unittest shards passed ({len(methods) + 53 + 71} tests)")
