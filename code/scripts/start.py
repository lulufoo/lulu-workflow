#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

from archive import run as run_archive
from workflow_common import (
    doc_dir,
    read_md_field,
    session_state_path,
    state_path,
    task_list_path,
    write_md_state,
    write_session_state,
)


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
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 5:
            continue
        task_id, title, target_file_raw, depends_raw, tdd_exempt_raw = cols[:5]
        task_id = task_id.strip()
        if not re.match(r"^t\d+$", task_id):
            continue
        # Strip backticks from target_file
        target_file = target_file_raw.strip().strip("`")
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
    parser.add_argument("--feature-id", required=True, help="Feature ID (from feature_init.py).")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    feature_id = args.feature_id.strip()

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=feature_id)
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
    ss_path = project_root / session_state_path(feature_id)
    if ss_path.exists():
        try:
            active_session = int(read_md_field(ss_path, "active_session", default="0")) + 1
        except ValueError:
            active_session = 1
    else:
        active_session = 1

    write_session_state(ss_path, active_session)

    # Create session directory
    s_dir = project_root / doc_dir(feature_id, active_session)
    s_dir.mkdir(parents=True, exist_ok=True)

    tl_path = project_root / task_list_path(feature_id, active_session)
    ws_path = project_root / state_path(feature_id, active_session)

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

        first_task = tasks[0]["id"] if tasks else ""
        write_md_state(
            ws_path,
            current_state="Executing",
            mode=args.mode,
            task_list_ref=tl_path.as_posix(),
            current_task=first_task,
            current_phase="WriteTests",
        )

        print(f"""
code session 已启动（Path B：task-from-work-order）。

会话状态文件：  {ss_path.as_posix()}
当前 session：  s{active_session}
状态文件：      {ws_path.as_posix()}
TDD 任务列表：  {tl_path.as_posix()}
任务数量：      {len(tasks)}
当前任务：      {first_task}
当前阶段：      WriteTests

下一步：
1. 读 code-task-list.md，向用户展示任务列表，等待确认
2. 用户确认后，从 {first_task} 开始执行 Phase 1（WriteTests）
""")

    else:  # task-from-tech
        write_md_state(
            ws_path,
            current_state="Executing",
            mode=args.mode,
            task_list_ref=tl_path.as_posix(),
            current_task="",
            current_phase="",
        )

        print(f"""
code session 已启动（Path A：task-from-tech）。

会话状态文件：  {ss_path.as_posix()}
当前 session：  s{active_session}
状态文件：      {ws_path.as_posix()}
TDD 任务列表：  {tl_path.as_posix()}（待生成）
tech-ref：      {args.tech_ref}

下一步：
1. 读 tech-doc.md（{args.tech_ref}）
2. 按 Test First 逻辑分析改动点，生成 {tl_path.as_posix()}
3. 向用户展示任务列表草稿，等待确认
4. 用户确认后，写入 code-task-list.md，更新 workflow-state.md（current_task / current_phase）
5. 从第一个任务开始执行 Phase 1（WriteTests）
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
