#!/usr/bin/env python3
"""Resolve Constraint material files before session enter (stdout JSON ``{"files":[...]}``)."""

from __future__ import annotations

import argparse
import json
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


_SKILL_DIR = Path(__file__).resolve().parents[1]
_SCRIPTS = _SKILL_DIR / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from material_docs import files_payload, resolve_material_files  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve Constraint material file list for lulu-approach.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--constraints",
        required=True,
        help="Path to lulu-approach constraints-*.json template.",
    )
    args = parser.parse_known_args()[0]
    apply_project_root_arg(args)
    return args


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    constraints_path = Path(args.constraints.strip()).expanduser().resolve()
    try:
        files = resolve_material_files(
            project_root, cycle_id, constraints_path, "constraint"
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(files_payload(files), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
