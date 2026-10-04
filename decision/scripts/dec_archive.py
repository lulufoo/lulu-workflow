#!/usr/bin/env python3
"""Restore/archive decision-family sessions using cycle-based cache layout.

Hot:  cache/<cycle_id>/<cache_subdir>/  (indexed via platform active-context.json)
Cold: cache/_archive/<conversation_id>/<cache_subdir>/

Stages: decision, lulu-bet, lulu-approach.
Does not scan legacy cache/decision/<conversation_id>/ paths.
"""

import argparse
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
for _parent in [_here, *_here.parents]:
    _scripts = _parent if (_parent / "project_root.py").is_file() else _parent / "scripts"
    if (_scripts / "project_root.py").is_file():
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        break
from project_root import apply_project_root_arg  # noqa: E402


from dec_archive_cycle import run_decision_cycle_archive


def run(
    project_root: Path,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> int:
    return run_decision_cycle_archive(
        project_root,
        exclude_conv_id,
        dry_run=dry_run,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore current decision conv from archive and move Delivered convs "
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
