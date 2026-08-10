#!/usr/bin/env python3
"""$DEC_REOPEN — leave Delivered/InProgress and set session Frozen (P1.3 A).

Separate from $DEC_START. Outer shell may call this on the target node and
on downstream sessions that must freeze together (P1.3a).

Uses Active Session (archive-1.1); no --session-dir on this CLI.
When holder constraints declare reopen_authorization=holder_required,
``--permit`` is mandatory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dec_domain_constraints_schema import resolve_stage
from dec_gate_control import cmd_reopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reopen a decision session into Frozen (then RS → $RS_COMMIT).",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (for Active / path resolution).",
    )
    parser.add_argument(
        "--permit",
        default="",
        help="Holder reopen permit path (required when reopen_authorization=holder_required).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    constraints_raw = args.constraints.strip()
    constraints_path = (
        Path(constraints_raw).expanduser().resolve() if constraints_raw else None
    )
    permit_raw = str(args.permit or "").strip()
    permit_path = Path(permit_raw).expanduser().resolve() if permit_raw else None
    try:
        stage = resolve_stage(constraints_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return cmd_reopen(
        project_root,
        args.cycle_id.strip(),
        stage,
        constraints_path=constraints_path,
        session_dir=None,
        permit_path=permit_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
