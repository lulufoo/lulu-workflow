#!/usr/bin/env python3

import argparse
from pathlib import Path

from archive import run as run_archive
from workflow_common import (
    read_md_field,
    session_state_path,
    state_path,
    write_active_context,
    write_md_state,
    write_session_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new work-order workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--feature-id", required=True, help="Feature ID (from feature_init.py).")
    parser.add_argument(
        "--tech-ref",
        required=True,
        help="Absolute path to the Delivered tech-doc.md that drives this work order.",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Cursor/Copilot conversation ID for active-context indexing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    feature_id = args.feature_id.strip()
    tech_ref = args.tech_ref.strip()

    if not Path(tech_ref).exists():
        print(f"错误：--tech-ref 文件不存在：{tech_ref}")
        return 1

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=feature_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    ss_path = project_root / session_state_path(feature_id)
    if ss_path.exists():
        try:
            active_doc = int(read_md_field(ss_path, "active_doc", default="0")) + 1
        except ValueError:
            active_doc = 1
    else:
        active_doc = 1

    write_session_state(ss_path, active_doc)
    write_active_context(
        project_root,
        feature_id,
        conversation_id=args.conversation_id.strip() or None,
    )

    ws_path = project_root / state_path(feature_id, active_doc)
    write_md_state(
        ws_path,
        "Drafting",
        evaluate_round=0,
        tech_ref=tech_ref,
    )

    print(f"""
会话已启动。

会话状态文件：{ss_path.as_posix()}
当前施工单：  r{active_doc}
状态文件：    {ws_path.as_posix()}
当前状态：    Drafting
评估轮次：    0
tech_ref：   {tech_ref}

进入 Drafting 后：
1. 读 workflow_config.json → work_order.task_template_url / tasklist_template_url
2. 读 tech-doc.md（全文）
3. 第一步：生成 task-list.md（等待用户确认任务拆分）
4. 用户确认后，逐个生成 tasks/t{{N}}/task.md
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
