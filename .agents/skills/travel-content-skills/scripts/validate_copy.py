#!/usr/bin/env python3
"""Validate a middle-aged and older audience narration contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from script_contract import load_json, validate_script


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 script JSON")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings exist",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        script = load_json(args.input)
        report = validate_script(script)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)

    if report["error_count"] or (args.strict and report["warning_count"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
