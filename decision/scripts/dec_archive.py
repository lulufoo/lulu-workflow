#!/usr/bin/env python3
"""Restore/archive decision-family sessions using cycle-based cache layout.

Hot:  cache/<cycle_id>/<cache_subdir>/  (indexed via platform active-context.json)
Cold: cache/_archive/<conversation_id>/<cache_subdir>/

Stages: diagnostic, lulu-bet, lulu-approach.
Does not scan legacy cache/decision/<conversation_id>/ paths.
"""

import argparse
import sys
from pathlib import Path

from dec_archive_cycle import run_diagnostic_cycle_archive


def run(
    project_root: Path,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> int:
    return run_diagnostic_cycle_archive(
        project_root,
        exclude_conv_id,
        dry_run=dry_run,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore current diagnostic conv from archive and move Delivered convs "
            "to cold storage (cycle-based layout)."
        ),
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument(
        "--exclude-conv-id",
        required=True,
        help="Current conversation ID (never archived; restored from cold if needed).",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run(
        Path(args.project_root).resolve(),
        exclude_conv_id=args.exclude_conv_id.strip(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
