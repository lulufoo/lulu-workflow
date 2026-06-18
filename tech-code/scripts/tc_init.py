#!/usr/bin/env python3
"""tech-code project init — workflow-config is applied via lulu-dev-workflow configure only."""

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="tech-code sub-init (no workflow-config writes).",
    )
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
