#!/usr/bin/env python3
"""$DEC_REOPEN — leave Delivered/InProgress and set session Frozen (P1.3 A).

Separate from $DEC_START. Outer shell may call this on the target node and
on downstream sessions that must freeze together (P1.3a).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dec_gate_control import cmd_reopen
from dec_session_paths import parse_session_dir_arg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reopen a decision session into Frozen (then RS → $RS_COMMIT).",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--stage",
        default="decision",
        help="Decision stage name (holder SKILL passes its name; default: decision).",
    )
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (used when --session-dir is omitted).",
    )
    parser.add_argument(
        "--session-dir",
        default="",
        help="Explicit nested session root (P1.1 A). When set, skips find_session_dir.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    constraints_raw = args.constraints.strip()
    constraints_path = (
        Path(constraints_raw).expanduser().resolve() if constraints_raw else None
    )
    session_dir = parse_session_dir_arg(args.session_dir, project_root)
    return cmd_reopen(
        project_root,
        args.cycle_id.strip(),
        args.stage.strip(),
        constraints_path=constraints_path,
        session_dir=session_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
