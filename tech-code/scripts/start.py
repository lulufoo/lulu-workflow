#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hook_guard import (  # noqa: E402
    check_gate,
    current_effective_delivered,
    get_sessions,
    get_topic_doc,
    load_stage_order,
    write_cycle_state,
)
from invalidation_hook import invalidate_downstream  # noqa: E402

from archive import run as run_archive
from session_state_schema import (
    load_work_order_round,
    next_session_round,
    save_session_state,
)
from workflow_state_schema import init_preparing, mark_historical
from workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    doc_dir,
    load_container_meta,
    session_state_path,
    state_path,
    task_list_path,
    write_active_context,
)


_TO_STAGE = "tech-code"



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

def parse_work_order_task_list(content: str):
    """
    Parse work-order task-list.md table rows.
    Table format:
      | task_id | 标题 | 目标文件 | 依赖 | TDD 豁免 |
      | t1      | ... | `file`  | —   | 否      |
    Returns list of dicts: {id, title, target_file, depends, tdd_exempt}
    """
    tasks = []
    in_table = False
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue
        # Skip header and separator rows
        if re.match(r"^\|[\s\-|]+\|$", line):
            continue
        if "task_id" in line or "------" in line:
            in_table = True
            continue
        in_table = True
        cols = _split_markdown_row(line)
        if len(cols) < 5:
            continue
        task_id, title, target_file_raw, depends_raw, tdd_exempt_raw = cols[:5]
        task_id = task_id.strip()
        if not re.match(r"^t\d+[a-z]*$", task_id):
            continue
        # Strip backticks from target_file
        target_file = target_file_raw.strip().replace("`", "")
        # Parse depends: "—" or "t1, t2"
        depends_raw = depends_raw.strip()
        depends = []
        if depends_raw and depends_raw != "—":
            depends = [d.strip() for d in depends_raw.split(",") if d.strip()]
        tdd_exempt = tdd_exempt_raw.strip() in ("是", "true", "True", "yes")
        tasks.append(
            {
                "id": task_id,
                "title": title.strip(),
                "target_file": target_file,
                "depends": depends,
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
        exempt_note = " [tdd_exempt]" if t.get("tdd_exempt") else ""
        lines.append(
            f"- [ ] {t['id']} · {t['title']} · `{t['target_file']}` · ⏳ Pending{dep_suffix}{exempt_note}"
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
    wo_ss_path = cache_dir / cycle_id / "tech" / "work-order" / "session-state.md"
    try:
        wo_active = load_work_order_round(wo_ss_path)
    except ValueError as e:
        print(f"错误：无法从 work-order session-state.md 推导 task-list-ref（{e}）", file=sys.stderr)
        return 1
    task_list_ref_path = cache_dir / cycle_id / "tech" / "work-order" / f"r{wo_active}" / "task-list.md"
    if not task_list_ref_path.exists():
        print(f"错误：task-list.md 不存在：{task_list_ref_path}", file=sys.stderr)
        return 1

    ss_path = project_root / session_state_path(cycle_id)
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

    init_preparing(
        ws_path,
        mode="work-order",
        task_list_ref=tl_path.as_posix(),
    )

    print(f"""
code session 已启动。

会话状态文件：  {ss_path.as_posix()}
当前 session：  s{active_session}
状态文件：      {ws_path.as_posix()}（current_state: Preparing）
code 任务列表：  {tl_path.as_posix()}
任务数量：      {len(tasks)}

下一步（L1 — Preparing，start.py 不执行 git）：
1. 读 code-task-list.md，向用户展示任务列表，等待确认
2. Agent 按 SKILL L1 创建 worktree/分支（git pull --rebase && git worktree add），写入 s{active_session}/workspace.json
3. workflow-state.md → current_state: Executing；再设置 current_task / current_phase（首任务 WriteTests）
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
