#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cycle_schema import write_stage as write_cycle_state  # noqa: E402
from invalidation_hook import invalidate_downstream  # noqa: E402
from start_gate import check_gate, get_topic_doc  # noqa: E402
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import current_effective_delivered, get_sessions, parse_frontmatter  # noqa: E402

from dx_archive import run as archive_diagnostic_session
from dx_gate_control import cmd_init_session, cmd_migrate_session
from dx_migrate_session import needs_migration
from dx_workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    load_container_meta,
    session_base_dir,
    session_state_path,
    write_active_context,
    write_session_state,
)


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
    parser = argparse.ArgumentParser(description="Start a diagnostic workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID (from cycle_init.py).")
    parser.add_argument(
        "--stage",
        default="diagnostic",
        help="Diagnostic stage name (e.g. product-diagnostic, tech-diagnostic, diagnostic).",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Cursor/Copilot conversation ID for active-context indexing.",
    )
    return parser.parse_known_args()[0]


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()
    conversation_id = args.conversation_id.strip()

    cycle_type = detect_cycle_type(cycle_id)
    cache_dir = project_root / CACHE_DIR
    try:
        load_container_meta(cache_dir, cycle_id, cycle_type)
    except ValueError as e:
        print(f"错误：{e}")
        return 1

    if conversation_id:
        # archive: deferred when --conversation-id omitted; enabled below when provided
        archive_rc = archive_diagnostic_session(
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

    # Step 5: get_topic_doc (feature containers only, if topic_id exists)
    try:
        topic_doc = get_topic_doc(cycle_id, stage, cache_dir)
        if topic_doc:
            print(f"Topic doc: {topic_doc}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    session_dir = project_root / session_base_dir(cycle_id, stage)
    ss_path = project_root / session_state_path(cycle_id, stage)

    if needs_migration(session_dir):
        migrate_rc = cmd_migrate_session(project_root, cycle_id, stage)
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
        if state == "InProgress":
            print("错误：会话已在进行中，请勿重复 start。", file=sys.stderr)
            return 1

    init_rc = cmd_init_session(project_root, cycle_id, stage)
    if init_rc != 0:
        return init_rc

    write_session_state(ss_path, "InProgress")
    write_active_context(
        project_root,
        cycle_id,
        conversation_id=conversation_id or None,
        stage=stage,
        cycle_type=cycle_type,
    )
    write_cycle_state(cycle_id, stage, cache_dir)

    print(f"""
诊断会话已启动。

会话状态文件：{ss_path.as_posix()}
当前状态：InProgress

工作流已就绪，可以开始 DDF 节点执行。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
