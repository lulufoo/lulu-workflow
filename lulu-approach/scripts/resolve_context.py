#!/usr/bin/env python3
"""Resolve lulu-approach's context.docs before handing off to decision.

``context.docs`` is auto-derived from ``(cycle_id, stage)`` by the shared
kernel resolver (``scripts/context_loading.py``), then stripped of Context /
Constraint material keys (``product_spec`` / ``tech_arch`` — loaded via
``resolve_context_docs`` / ``resolve_constraint_docs`` instead). The session
directory is the approach root.

Writes ``{"context": {"docs": {...}}}`` to a file and prints that file's path
to stdout for ``$DEC_START`` (``--domain-constraints-file``).
"""

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
_WORKFLOW_ROOT = _SKILL_DIR.parent
_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_APPROACH_SCRIPTS = _SKILL_DIR / "scripts"
if str(_APPROACH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_APPROACH_SCRIPTS))
_DECISION_SCRIPTS = _WORKFLOW_ROOT / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from context_loading import build_context_loading  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402

from approach_layout import APPROACH_CACHE_SUBDIR  # noqa: E402
from dec_domain_constraints_schema import load_constraints_config  # noqa: E402
from dec_io import atomic_write_text  # noqa: E402
from material_docs import strip_binding_excluded  # noqa: E402

STAGE = "lulu-approach"
_RESOLVED_CONTEXT_FILENAME = "resolved-context.json"


def _require_approach_root(session_dir: Path | None) -> None:
    if session_dir is None:
        return
    name = Path(session_dir).resolve().name
    if name != APPROACH_CACHE_SUBDIR:
        raise ValueError(f"session_dir must be the approach root, got {session_dir}")


def resolve(
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    *,
    session_dir: Path | None = None,
) -> dict:
    """Compute the resolved ``{"context": {"docs": {...}}}`` payload."""
    load_constraints_config(constraints_path)
    cache_dir = project_root / platform_cache_dir(detect_platform())
    context = build_context_loading(cycle_id, STAGE, cache_dir=cache_dir)
    docs = strip_binding_excluded(dict(context.get("docs") or {}))
    _require_approach_root(session_dir)
    return {"context": {"docs": docs}}


def resolved_context_file_path(
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    *,
    binding_id: str | None = None,
) -> Path:
    constraints = load_constraints_config(constraints_path)
    cache_dir = project_root / platform_cache_dir(detect_platform())
    cache_subdir = constraints["cache_subdir"]
    stage_outer = cache_dir / cycle_id / cache_subdir
    bid = str(binding_id or "").strip()
    if bid:
        return stage_outer / "bindings" / bid / _RESOLVED_CONTEXT_FILENAME
    return stage_outer / _RESOLVED_CONTEXT_FILENAME


def write_resolved_context(
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    *,
    session_dir: Path | None = None,
    binding_id: str | None = None,
) -> Path:
    payload = resolve(
        project_root,
        cycle_id,
        constraints_path,
        session_dir=session_dir,
    )
    path = resolved_context_file_path(
        project_root,
        cycle_id,
        constraints_path,
        binding_id=binding_id,
    )
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve lulu-approach's context.docs map.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument(
        "--constraints",
        required=True,
        help="Path to lulu-approach constraints-*.json template.",
    )
    parser.add_argument(
        "--session-dir",
        default="",
        help="Session directory. The approach root is the session.",
    )
    parser.add_argument(
        "--binding-id",
        default="",
        help="When set, write under bindings/<binding_id>/resolved-context.json.",
    )
    args = parser.parse_known_args()[0]
    apply_project_root_arg(args)
    return args


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    constraints_path = Path(args.constraints.strip()).expanduser().resolve()
    session_raw = str(args.session_dir or "").strip()
    session_dir = Path(session_raw).expanduser().resolve() if session_raw else None
    binding_id = str(getattr(args, "binding_id", "") or "").strip() or None
    try:
        path = write_resolved_context(
            project_root,
            cycle_id,
            constraints_path,
            session_dir=session_dir,
            binding_id=binding_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
