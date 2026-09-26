#!/usr/bin/env python3
"""Resolve lulu-bet's context.docs before handing off to decision.

``context.docs`` is auto-derived from ``(cycle_id, stage)`` by the shared
kernel resolver (``scripts/context_loading.py``). This script validates the
constraints template, writes ``{"context": {"docs": {...}}}`` to a file, and
prints that file's path for ``$DEC_START --domain-constraints-file``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SKILL_DIR.parent
_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_DECISION_SCRIPTS = _WORKFLOW_ROOT / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from context_loading import build_context_loading  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402

from dec_domain_constraints_schema import load_constraints_config  # noqa: E402
from dec_io import atomic_write_text  # noqa: E402

STAGE = "lulu-bet"
_RESOLVED_CONTEXT_FILENAME = "resolved-context.json"


def resolve(project_root: Path, cycle_id: str, constraints_path: Path) -> dict:
    """Compute the resolved ``{"context": {...}}`` payload (no filesystem writes)."""
    load_constraints_config(constraints_path)  # validate template only
    cache_dir = project_root / platform_cache_dir(detect_platform())
    return {
        "context": build_context_loading(cycle_id, STAGE, cache_dir=cache_dir),
    }


def resolved_context_file_path(project_root: Path, cycle_id: str, constraints_path: Path) -> Path:
    """Where the resolved payload lands — same cache subdir as the eventual
    session's own domain-constraints.json (see dec_workflow_common.session_base_dir),
    computed from the constraints template's own ``cache_subdir`` field since no
    session exists yet at resolve time."""
    constraints = load_constraints_config(constraints_path)
    cache_dir = project_root / platform_cache_dir(detect_platform())
    cache_subdir = constraints["cache_subdir"]
    return cache_dir / cycle_id / cache_subdir / _RESOLVED_CONTEXT_FILENAME


def write_resolved_context(project_root: Path, cycle_id: str, constraints_path: Path) -> Path:
    """Resolve and persist the context payload, returning its file path.

    Kept on disk after decision consumes it (not cleaned up) — it doubles as
    an inspectable audit trail of what was resolved at session-start time,
    consistent with every other cache artifact in this workflow.
    """
    payload = resolve(project_root, cycle_id, constraints_path)
    path = resolved_context_file_path(project_root, cycle_id, constraints_path)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve lulu-bet's context sources.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--constraints",
        required=True,
        help="Path to lulu-bet constraints-*.json template.",
    )
    return parser.parse_known_args()[0]


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    constraints_path = Path(args.constraints.strip()).expanduser().resolve()
    try:
        path = write_resolved_context(project_root, cycle_id, constraints_path)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
