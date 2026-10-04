#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from project_root import apply_project_root_arg  # noqa: E402

from archive_common import TECH_WORK_ORDER_CONFIG as WORK_ORDER_CONFIG, run_archive  # noqa: E402


def run(
    project_root: Path,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> int:
    return run_archive(project_root, WORK_ORDER_CONFIG, exclude_conv_id, dry_run=dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore current work-order conv from archive and move Delivered convs to cold storage.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument(
        "--exclude-conv-id",
        required=True,
        help="Current conversation ID (never archived; restored from cold if needed).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply_project_root_arg(args)
    return args


def main() -> int:
    args = parse_args()
    return run(
        Path(args.project_root).resolve(),
        exclude_conv_id=args.exclude_conv_id.strip(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
