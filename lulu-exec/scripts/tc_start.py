#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cycle_log_schema import append_cycle_log  # noqa: E402
from cycle_schema import write_stage as write_cycle_state  # noqa: E402
from invalidation_hook import invalidate_downstream  # noqa: E402
from start_gate import check_gate, get_topic_doc  # noqa: E402
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import current_effective_delivered, get_sessions  # noqa: E402

from tc_archive import run as run_archive
from tc_session_state_schema import (
    load_session_state,
    load_work_order_round,
    next_session_round,
    save_session_state,
)
from tc_workflow_state_schema import (
    init_starting,
    load_workflow_state,
    mark_historical,
    save_workflow_state,
)
from tc_workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    doc_dir,
    load_container_meta,
    session_state_path,
    state_path,
    task_list_path,
    write_active_context,
)
from stage_identity import EXEC_STAGE  # noqa: E402


_TO_STAGE = EXEC_STAGE



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
    mark_historical(latest.state_path)


# ---------------------------------------------------------------------------
# task-list.md parsing
# ---------------------------------------------------------------------------

def _header_has_kind(content: str) -> bool:
    for line in content.splitlines():
        if line.startswith("|") and "task_id" in line:
            return "kind" in line.lower()
    return False


def parse_work_order_task_list(content: str):
    """
    Parse work-order task-list.md table rows.
    Current format:
      | task_id | Title | Target File | Dependencies | Kind | TDD Exempt |
    Legacy format (5 columns): last column is TDD Exempt, kind defaults to coding.
    """
    has_kind = _header_has_kind(content)
    tasks = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[\s\-|]+\|$", line):
            continue
        if "task_id" in line or "------" in line:
            continue
        cols = _split_markdown_row(line)
        if len(cols) < 5:
            continue
        task_id = cols[0].strip()
        if not re.match(r"^t\d+[a-z]*$", task_id):
            continue
        title = cols[1].strip()
        target_file = cols[2].strip().replace("`", "")
        depends_raw = cols[3].strip()
        depends = []
        if depends_raw and depends_raw != "—":
            depends = [d.strip() for d in depends_raw.split(",") if d.strip()]
        if has_kind and len(cols) >= 6:
            kind_raw = cols[4].strip()
            kind = kind_raw if kind_raw in ("coding", "action") else "coding"
            tdd_exempt_raw = cols[5]
        else:
            kind = "coding"
            tdd_exempt_raw = cols[4]
        tdd_exempt = tdd_exempt_raw.strip() in ("是", "true", "True", "yes")
        tasks.append(
            {
                "id": task_id,
                "title": title,
                "target_file": target_file,
                "depends": depends,
                "kind": kind,
                "tdd_exempt": tdd_exempt,
            }
        )
    return tasks


def _split_markdown_row(line: str):
    cells = []
    current = []
    for char in line.strip().strip("|"):
        if char == "|" and (not current or current[-1] != "\\"):
            cells.append("".join(current).replace("\\|", "|").strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).replace("\\|", "|").strip())
    return cells


def build_code_task_list_md(tasks, source: str, task_list_ref: str) -> str:
    """Build initial code-task-list.md content from parsed tasks."""
    total = len(tasks)
    lines = [
        "---",
        f"source: {source}",
        f"task_list_ref: {task_list_ref}",
        f"total: {total}",
        "done: 0",
        "---",
        "",
        "# Code Task List",
        "",
    ]
    for t in tasks:
        dep_suffix = ""
        if t["depends"]:
            dep_suffix = f" (depends: {', '.join(t['depends'])})"
        kind_note = " [action]" if t.get("kind") == "action" else ""
        exempt_note = " [tdd_exempt]" if t.get("tdd_exempt") else ""
        lines.append(
            f"- [ ] {t['id']} · {t['title']} · `{t['target_file']}` · ⏳ Pending{dep_suffix}{kind_note}{exempt_note}"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new TDD workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID (from cycle_init.py).")
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

    cycle_type = detect_cycle_type(cycle_id)
    cache_dir = project_root / CACHE_DIR
    try:
        load_container_meta(cache_dir, cycle_id, cycle_type)
    except ValueError as e:
        print(f"错误：{e}")
        return 1

    # Step 2: re-open detection
    if current_effective_delivered(cycle_id, _TO_STAGE, cache_dir):
        _mark_historical(cycle_id, _TO_STAGE, cache_dir)
        invalidate_downstream(cycle_id, _TO_STAGE, cycle_type, cache_dir)

    # Step 3: back-fill detection
    latest_stage = _find_latest_delivered_stage(cycle_id, cycle_type, cache_dir)
    if latest_stage:
        try:
            _stages = load_stage_order(cycle_type)
        except Exception:
            _stages = []
        if _TO_STAGE in _stages and latest_stage in _stages:
            if _stages.index(_TO_STAGE) < _stages.index(latest_stage):
                invalidate_downstream(cycle_id, _TO_STAGE, cycle_type, cache_dir)

    # Step 4: check_gate
    ok, reason = check_gate(cycle_id, _TO_STAGE, cycle_type, cache_dir)
    if not ok:
        print(f"Gate blocked: {reason}", file=sys.stderr)
        sys.exit(1)

    # Step 5: get_topic_doc (feature containers only, if topic_id exists)
    try:
        topic_doc = get_topic_doc(cycle_id, _TO_STAGE, cache_dir)
        if topic_doc:
            print(f"Topic doc: {topic_doc}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=cycle_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    # Derive task-list.md path from work-order session-state.md
    wo_ss_path = cache_dir / cycle_id / "lulu-tasks" / "session-state.md"
    try:
        wo_active = load_work_order_round(wo_ss_path)
    except ValueError as e:
        print(f"错误：无法从 work-order session-state.md 推导 task-list-ref（{e}）", file=sys.stderr)
        return 1
    task_list_ref_path = cache_dir / cycle_id / "lulu-tasks" / f"r{wo_active}" / "task-list.md"
    if not task_list_ref_path.exists():
        print(f"错误：task-list.md 不存在：{task_list_ref_path}", file=sys.stderr)
        return 1

    ss_path = project_root / session_state_path(cycle_id)

    if ss_path.exists():
        try:
            prev_active = load_session_state(ss_path)
            prev_ws = project_root / state_path(cycle_id, prev_active)
            if prev_ws.exists():
                prev_state = load_workflow_state(prev_ws)
                if prev_state["current_state"] != "Delivered":
                    print(
                        f"superseding s{prev_active} in {prev_state['current_state']}, "
                        f"creating s{prev_active + 1}",
                        file=sys.stderr,
                    )
        except ValueError:
            pass

    active_session = next_session_round(ss_path)
    save_session_state(ss_path, active_session)
    write_active_context(
        project_root,
        cycle_id,
        conversation_id=args.conversation_id.strip() or None,
        cycle_type=cycle_type,
    )
    write_cycle_state(cycle_id, _TO_STAGE, cache_dir)

    # Create session directory
    s_dir = project_root / doc_dir(cycle_id, active_session)
    s_dir.mkdir(parents=True, exist_ok=True)

    tl_path = project_root / task_list_path(cycle_id, active_session)
    ws_path = project_root / state_path(cycle_id, active_session)

    task_list_content = task_list_ref_path.read_text(encoding="utf-8")
    tasks = parse_work_order_task_list(task_list_content)
    if not tasks:
        print("警告：task-list.md 中未解析到任何任务，请检查表格格式。")

    tdd_list_content = build_code_task_list_md(
        tasks,
        source="work-order",
        task_list_ref=task_list_ref_path.as_posix(),
    )
    tl_path.write_text(tdd_list_content, encoding="utf-8")

    init_starting(
        ws_path,
        mode="work-order",
        task_list_ref=tl_path.as_posix(),
        master_conversation_id=args.conversation_id.strip(),
    )

    conv_id = args.conversation_id.strip()
    if conv_id:
        append_cycle_log(
            cache_dir / cycle_id,
            level="INFO",
            stage=_TO_STAGE,
            message=f"code session s{active_session} started (master_conversation_id={conv_id})",
        )

    save_workflow_state(ws_path, {"current_state": "Preparing"})

    print(f"""
code session started.

session: s{active_session}
tasks: {len(tasks)}
current_state: Preparing
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
