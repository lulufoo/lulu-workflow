#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cycle_schema import write_stage as write_cycle_state  # noqa: E402
from invalidation_hook import invalidate_downstream  # noqa: E402
from start_gate import check_gate  # noqa: E402
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import current_effective_delivered, get_sessions, parse_frontmatter  # noqa: E402
from project_root import apply_project_root_arg  # noqa: E402

from dec_archive import run as archive_decision_session
from dec_domain_constraints_schema import resolve_stage
from dec_gate_control import cmd_init_session, cmd_migrate_session
from dec_migrate_session import needs_migration
from dec_workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    load_container_meta,
    session_base_dir,
    session_state_path,
    write_active_context,
    write_session_state,
)
from dec_session_paths import parse_session_dir_arg
from dec_session_state_schema import session_state_file



def _find_latest_delivered_stage(cycle_id: str, cycle_type: str,
                                  cache_dir: Path) -> "str | None":
    """Return the last stage in cycle order where current_effective_delivered is True."""
    try:
        stages = load_stage_order(cycle_type)
    except Exception:
        return None
    latest = None
    for s in stages:
        if current_effective_delivered(cycle_id, s, cache_dir):
            latest = s
    return latest


def _mark_historical(cycle_id: str, stage: str, cache_dir: Path) -> None:
    """Add historical: true to frontmatter of the current effective delivered session."""
    sessions = [s for s in get_sessions(cycle_id, stage, cache_dir)
                if s.state != "Invalidated"]
    if not sessions:
        return
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    if not latest.state_path or not latest.state_path.exists():
        return
    text = latest.state_path.read_text(encoding="utf-8")
    if "historical:" not in text:
        updated = re.sub(r"(---\s*\n)", r"\1historical: true\n", text, count=1)
        latest.state_path.write_text(updated, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a decision workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID (from cycle_init.py).")
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (required for holder stages such as lulu-bet and lulu-approach).",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Cursor/Copilot conversation ID for active-context indexing.",
    )
    parser.add_argument(
        "--domain-constraints-file",
        default="",
        help=(
            "Optional path to a JSON file containing a domain-constraints override, "
            "written to disk by the holder's own resolver script (e.g. resolve_context.py) "
            "— decision performs no path resolution itself, it only reads this file as-is "
            "at init time. Never pass JSON content directly on the command line."
        ),
    )
    parser.add_argument(
        "--session-dir",
        default="",
        help=(
            "Explicit nested session root (P1.1 A). When set, skips find_session_dir "
            "and initializes artifacts under this directory."
        ),
    )
    args = parser.parse_known_args()[0]
    apply_project_root_arg(args)
    return args


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


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    conversation_id = args.conversation_id.strip()
    constraints_path = Path(args.constraints.strip()).expanduser().resolve() if args.constraints.strip() else None
    try:
        stage = resolve_stage(constraints_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    cycle_type = detect_cycle_type(cycle_id)
    cache_dir = project_root / CACHE_DIR
    try:
        load_container_meta(cache_dir, cycle_id, cycle_type)
    except ValueError as e:
        print(f"错误：{e}")
        return 1

    if conversation_id:
        # archive: deferred when --conversation-id omitted; enabled below when provided
        archive_rc = archive_decision_session(
            project_root,
            exclude_conv_id=conversation_id,
        )
        if archive_rc != 0:
            return archive_rc
    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=conversation_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    # Step 2: re-open detection
    if current_effective_delivered(cycle_id, stage, cache_dir):
        _mark_historical(cycle_id, stage, cache_dir)
        invalidate_downstream(cycle_id, stage, cycle_type, cache_dir)

    # Step 3: back-fill detection
    latest_stage = _find_latest_delivered_stage(cycle_id, cycle_type, cache_dir)
    if latest_stage:
        try:
            _stages = load_stage_order(cycle_type)
        except Exception:
            _stages = []
        if stage in _stages and latest_stage in _stages:
            if _stages.index(stage) < _stages.index(latest_stage):
                invalidate_downstream(cycle_id, stage, cycle_type, cache_dir)

    # Step 4: check_gate
    ok, reason = check_gate(cycle_id, stage, cycle_type, cache_dir)
    if not ok:
        print(f"Gate blocked: {reason}", file=sys.stderr)
        sys.exit(1)

    try:
        domain_override = _load_domain_override_file(args.domain_constraints_file.strip())
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"错误：--domain-constraints-file {e}", file=sys.stderr)
        return 1

    session_dir_override = parse_session_dir_arg(args.session_dir, project_root)
    if session_dir_override is not None:
        session_dir = session_dir_override
        ss_path = session_state_file(session_dir)
    else:
        session_dir = project_root / session_base_dir(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        )
        ss_path = project_root / session_state_path(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        )

    if needs_migration(session_dir):
        migrate_rc = cmd_migrate_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
            session_dir=session_dir_override if session_dir_override is not None else session_dir,
        )
        if migrate_rc != 0:
            return migrate_rc
        write_active_context(
            project_root,
            cycle_id,
            conversation_id=conversation_id or None,
            stage=stage,
            cycle_type=cycle_type,
        )
        write_cycle_state(cycle_id, stage, cache_dir)
        print(f"""
旧版诊断会话已迁移至 gate-state 架构。

会话目录：{session_dir.as_posix()}
请继续执行当前 active_gate 对应的 runner。
""")
        return 0

    if ss_path.exists() and (session_dir / "gate-state.json").exists():
        state = parse_frontmatter(ss_path.read_text(encoding="utf-8")).get("current_state", "")
        if state in ("InProgress", "Frozen"):
            print(
                f"错误：会话状态为 {state}，请勿重复 start"
                + ("；Delivered 后重开请用 $DEC_REOPEN。" if state == "Frozen" else "。"),
                file=sys.stderr,
            )
            return 1

    init_rc = cmd_init_session(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        domain_override=domain_override,
        session_dir=session_dir_override,
        commit_active=False,
    )
    if init_rc != 0:
        return init_rc

    write_session_state(ss_path, "InProgress")

    from dec_active_control import _commit_active  # noqa: WPS433

    try:
        _commit_active(
            project_root,
            cycle_id,
            stage,
            session_dir=session_dir,
            constraints_path=constraints_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误：设置 Active Session 失败：{exc}", file=sys.stderr)
        return 1

    write_active_context(
        project_root,
        cycle_id,
        conversation_id=conversation_id or None,
        stage=stage,
        cycle_type=cycle_type,
    )
    write_cycle_state(cycle_id, stage, cache_dir)

    # context_docs already emitted by cmd_init_session stdout JSON
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
