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
)
from invalidation_hook import invalidate_downstream  # noqa: E402

from archive import run as run_archive
from workflow_common import (
    CACHE_DIR,
    detect_cycle_type,
    doc_dir,
    load_container_meta,
    read_md_field,
    session_state_path,
    state_path,
    task_list_path,
    write_active_context,
    write_md_state,
    write_session_state,
)


_TO_STAGE = "tech-code"
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _find_latest_delivered_stage(cycle_id: str, cycle_type: str,
                                  cache_dir: Path) -> "str | None":
    """Return the last stage in cycle order where current_effective_delivered is True."""
    try:
        stages = load_stage_order(cycle_type, _CONFIG_DIR)
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
    ws_path = cache_dir / cycle_id / stage / latest.revision / "workflow-state.md"
    if not ws_path.exists():
        return
    text = ws_path.read_text(encoding="utf-8")
    if "historical:" not in text:
        updated = re.sub(r"(---\s*\n)", r"\1historical: true\n", text, count=1)
        ws_path.write_text(updated, encoding="utf-8")


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
        "--mode",
        required=True,
        choices=["task-from-work-order", "task-from-tech"],
        help="Input mode: task-from-work-order or task-from-tech.",
    )
    # Path B
    parser.add_argument(
        "--task-list-ref",
        default="",
        help="(Path B) Absolute path to work-order task-list.md.",
    )
    parser.add_argument(
        "--task-refs",
        nargs="*",
        default=[],
        help="(Path B) Absolute paths to individual task.md files.",
    )
    # Path A
    parser.add_argument(
        "--tech-ref",
        default="",
        help="(Path A) Absolute path to tech-doc.md.",
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
            _stages = load_stage_order(cycle_type, _CONFIG_DIR)
        except Exception:
            _stages = []
        if _TO_STAGE in _stages and latest_stage in _stages:
            if _stages.index(_TO_STAGE) < _stages.index(latest_stage):
                invalidate_downstream(cycle_id, _TO_STAGE, cycle_type, cache_dir)

    # Step 4: check_gate
    ok, reason = check_gate(cycle_id, _TO_STAGE, cycle_type, cache_dir, _CONFIG_DIR)
    if not ok:
        print(f"Gate blocked: {reason}", file=sys.stderr)
        sys.exit(1)

    # Step 5: get_topic_doc (feature containers only, if topic_id exists)
    try:
        topic_doc = get_topic_doc(cycle_id, _TO_STAGE, cache_dir, _CONFIG_DIR)
        if topic_doc:
            print(f"Topic doc: {topic_doc}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=cycle_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    # Validate mode-specific required args
    if args.mode == "task-from-work-order":
        if not args.task_list_ref:
            print("错误：--mode task-from-work-order 需要提供 --task-list-ref")
            return 1
        task_list_ref_path = Path(args.task_list_ref)
        if not task_list_ref_path.exists():
            print(f"错误：--task-list-ref 文件不存在：{args.task_list_ref}")
            return 1
    elif args.mode == "task-from-tech":
        if not args.tech_ref:
            print("错误：--mode task-from-tech 需要提供 --tech-ref")
            return 1
        if not Path(args.tech_ref).exists():
            print(f"错误：--tech-ref 文件不存在：{args.tech_ref}")
            return 1

    # Determine session round
    ss_path = project_root / session_state_path(cycle_id)
    if ss_path.exists():
        try:
            active_session = int(read_md_field(ss_path, "active_session", default="0")) + 1
        except ValueError:
            active_session = 1
    else:
        active_session = 1

    write_session_state(ss_path, active_session)
    write_active_context(
        project_root,
        cycle_id,
        conversation_id=args.conversation_id.strip() or None,
        cycle_type=cycle_type,
    )

    # Create session directory
    s_dir = project_root / doc_dir(cycle_id, active_session)
    s_dir.mkdir(parents=True, exist_ok=True)

    tl_path = project_root / task_list_path(cycle_id, active_session)
    ws_path = project_root / state_path(cycle_id, active_session)

    if args.mode == "task-from-work-order":
        # Parse task-list.md and generate code-task-list.md
        task_list_content = task_list_ref_path.read_text(encoding="utf-8")
        tasks = parse_work_order_task_list(task_list_content)
        if not tasks:
            print("警告：task-list.md 中未解析到任何任务，请检查表格格式。")

        tdd_list_content = build_code_task_list_md(
            tasks,
            source="work-order",
            task_list_ref=args.task_list_ref,
        )
        tl_path.write_text(tdd_list_content, encoding="utf-8")

        write_md_state(
            ws_path,
            current_state="Preparing",
            mode=args.mode,
            task_list_ref=tl_path.as_posix(),
            current_task="",
            current_phase="",
        )

        print(f"""
code session 已启动（Path B：task-from-work-order）。

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

    else:  # task-from-tech
        write_md_state(
            ws_path,
            current_state="Preparing",
            mode=args.mode,
            task_list_ref=tl_path.as_posix(),
            current_task="",
            current_phase="",
        )

        print(f"""
code session 已启动（Path A：task-from-tech）。

会话状态文件：  {ss_path.as_posix()}
当前 session：  s{active_session}
状态文件：      {ws_path.as_posix()}（current_state: Preparing）
code 任务列表：  {tl_path.as_posix()}（待生成）
tech-ref：      {args.tech_ref}

下一步：
1. 读 tech-doc.md（{args.tech_ref}）
2. 按 Test First 逻辑分析改动点，生成 {tl_path.as_posix()}
3. 向用户展示任务列表草稿，等待确认
4. L1：worktree + workspace.json（见 SKILL）；再 Preparing → Executing
5. 用户确认后写入 code-task-list.md，设置 current_task / current_phase，开始 WriteTests
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
