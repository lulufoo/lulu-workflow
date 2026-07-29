#!/usr/bin/env python3
"""Active Session control (archive-1.1).

Subcommands:
    set-active   Bind Active to --session-dir (required); optional
                 --domain-constraints-file refreshes context.docs (C7)
    get-active   Print current Active absolute path
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dec_active_session_schema import (
    is_valid_session_root,
    relative_session_dir_for,
    save_active_session,
)
from dec_domain_constraints_schema import (
    context_docs_map,
    load_domain_constraints,
    merge_domain_constraints,
    save_domain_constraints,
)
from dec_session_paths import (
    parse_session_dir_arg,
    resolve_active_session_dir,
    stage_outer_root,
)
from dec_workflow_common import CACHE_DIR


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _load_domain_override_file(raw_path: str) -> dict[str, Any] | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"--domain-constraints-file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("--domain-constraints-file content must be a JSON object")
    return data


def _refresh_session_context(session_dir: Path, override: dict[str, Any]) -> dict[str, str]:
    """Merge holder override into session domain-constraints; return context_docs."""
    dc_path = Path(session_dir) / "domain-constraints.json"
    if not dc_path.is_file():
        raise FileNotFoundError(f"domain-constraints not found: {dc_path}")
    base = load_domain_constraints(dc_path)
    merged = merge_domain_constraints(base, override)
    save_domain_constraints(dc_path, merged)
    return context_docs_map(merged)


def set_active_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    session_dir: Path,
    constraints_path: Path | None = None,
    domain_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist Active pointing at session_dir; return result dict with context_docs."""
    target = Path(session_dir).resolve()
    if not is_valid_session_root(target):
        raise ValueError(
            f"target is not a valid decision session root "
            f"(need gate-state.json or domain-constraints.json): {target}"
        )
    outer = stage_outer_root(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
    )
    rel = relative_session_dir_for(outer, target)
    payload = save_active_session(outer, rel)

    docs: dict[str, str] = {}
    if domain_override is not None:
        docs = _refresh_session_context(target, domain_override)
    else:
        dc_path = target / "domain-constraints.json"
        if dc_path.is_file():
            docs = context_docs_map(load_domain_constraints(dc_path))

    return {
        "ok": True,
        "active_session": payload,
        "session_dir": target.as_posix(),
        "stage_outer": outer.as_posix(),
        "context_docs": docs,
    }


def get_active_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
) -> dict[str, Any]:
    outer = stage_outer_root(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
    )
    target = resolve_active_session_dir(outer)
    from dec_active_session_schema import load_active_session  # noqa: WPS433

    payload = load_active_session(outer)
    docs: dict[str, str] = {}
    dc_path = target / "domain-constraints.json"
    if dc_path.is_file():
        try:
            docs = context_docs_map(load_domain_constraints(dc_path))
        except (FileNotFoundError, ValueError):
            docs = {}
    return {
        "ok": True,
        "active_session": payload,
        "session_dir": target.as_posix(),
        "stage_outer": outer.as_posix(),
        "context_docs": docs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decision Active Session control.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument("--stage", default="decision", help="Decision stage name.")
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (for stage outer resolution).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    set_p = sub.add_parser("set-active", help="Set Active Session to --session-dir.")
    set_p.add_argument(
        "--session-dir",
        required=True,
        help="Absolute or project-relative nested session root (main/ or Dx/).",
    )
    set_p.add_argument(
        "--domain-constraints-file",
        default="",
        help=(
            "Optional holder-resolved context override (re-parse on bind / C7). "
            "When set, merges into the session domain-constraints.json."
        ),
    )
    sub.add_parser("get-active", help="Print current Active Session path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()
    constraints_path = (
        Path(args.constraints.strip()).expanduser().resolve()
        if args.constraints.strip()
        else None
    )
    try:
        if args.command == "set-active":
            session_dir = parse_session_dir_arg(args.session_dir, project_root)
            if session_dir is None:
                return _emit_error("--session-dir is required")
            override = _load_domain_override_file(
                str(getattr(args, "domain_constraints_file", "") or "").strip()
            )
            result = set_active_session(
                project_root,
                cycle_id,
                stage,
                session_dir=session_dir,
                constraints_path=constraints_path,
                domain_override=override,
            )
            _emit(result)
            return 0
        if args.command == "get-active":
            result = get_active_session(
                project_root,
                cycle_id,
                stage,
                constraints_path=constraints_path,
            )
            _emit(result)
            return 0
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    return _emit_error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
