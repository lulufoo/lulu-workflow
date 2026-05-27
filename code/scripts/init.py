#!/usr/bin/env python3

import argparse
from pathlib import Path

from workflow_common import (
    resolve_workflow_config_path,
    read_json,
    write_json,
)

CODE_CONFIG_DEFAULTS = {
    "test_command": "npm test",
    "woqa_url": "",
    "git": {
        "worktree_base": ".cache/worktrees",
        "branch_pattern": "wt/{type}-{slug}",
        "default_type": "feat",
        "commit_message_template": "feat({scope}): {task_id} {summary}",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize code workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    config_path = resolve_workflow_config_path(project_root)
    config = read_json(config_path, default={})
    if "code" not in config:
        config["code"] = CODE_CONFIG_DEFAULTS
        write_json(config_path, config)
        config_note = f"已添加 code 配置区块到 {config_path.as_posix()}"
    else:
        config_note = f"code 配置区块已存在，跳过（{config_path.as_posix()}）"

    start_py = Path(__file__).resolve().parent / "start.py"
    print(f"""
code workflow 初始化完成。

{config_note}

下一步：
1. 检查 {config_path.as_posix()} 中的 code 区块：
   - test_command：运行测试的命令（默认 npm test，按项目修改）
   - code.git：worktree_base、branch_pattern、default_type、commit_message_template
   - woqa_url：可选质量审计框架文档 URL

2. 启动 code session，运行 start 命令：

   Path B（来自 work-order）：
   python3 {start_py} \
     --project-root "$(pwd)" \
     --feature-id "<feature_id>" \
     --mode task-from-work-order \
     --task-list-ref "<abs-path-to-task-list.md>" \
     --task-refs "<abs-path-to-t1/task.md>" "<abs-path-to-t2/task.md>"

   Path A（来自 tech-doc）：
   python3 {start_py} \
     --project-root "$(pwd)" \
     --feature-id "<feature_id>" \
     --mode task-from-tech \
     --tech-ref "<abs-path-to-tech-doc.md>"
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
