#!/usr/bin/env python3
"""Run all automated tests in the skill collection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SUITES = [
    (".agents/skills/travel-content-skills/tests", "test_*.py"),
]


def main() -> int:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    failures = 0

    for relative, pattern in SUITES:
        print(f"\n=== {relative} ===", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(REPO_ROOT / relative),
                "-p",
                pattern,
                "-v",
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=False,
        )
        failures += completed.returncode != 0

    if failures:
        print(f"\nFAIL: {failures} suite(s) failed")
        return 1

    print(f"\nPASS: {len(SUITES)} test suite(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
