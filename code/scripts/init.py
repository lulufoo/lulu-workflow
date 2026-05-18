#!/usr/bin/env python3

import argparse
from pathlib import Path

from workflow_common import (
    CONFIG_PATH,
    HOOKS_JSON_PATH,
    HOOK_COMMAND,
    merge_hook_entry,
    read_json,
    write_json,
)

TDD_CONFIG_DEFAULTS = {
    "test_command": "npm test",
    "woqa_url": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize TDD workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    config_path = project_root / CONFIG_PATH
    config = read_json(config_path, default={})
    if "tdd" not in config:
        config["code"] = TDD_CONFIG_DEFAULTS
        write_json(config_path, config)
        config_note = f"已添加 tdd 配置区块到 {config_path.as_posix()}"
    else:
        config_note = f"code 配置区块已存在，跳过（{config_path.as_posix()}）"

    hooks_path = project_root / HOOKS_JSON_PATH
    hooks_payload = read_json(hooks_path, default={"version": 1, "hooks": {}})
    merged = merge_hook_entry(hooks_payload)
    write_json(hooks_path, merged)

    start_py = Path(__file__).resolve().parent / "start.py"
    print(f"""
TDD workflow 初始化完成。

{config_note}
Hook 已注册：{HOOK_COMMAND}

下一步：
1. 检查 {config_path.as_posix()} 中的 code 区块：
   - test_command：运行测试的命令（默认 npm test，按项目修改）
   - woqa_url：TDD 执行质量审计框架文档 URL

2. 启动 TDD session，运行 start 命令：

   Path B（来自 work-order）：
   python3 {start_py} \\
     --project-root "$(pwd)" \\
     --conversation-id "<uuid>" \\
     --mode task-from-work-order \\
     --task-list-ref "<abs-path-to-task-list.md>" \\
     --task-refs "<abs-path-to-t1/task.md>" "<abs-path-to-t2/task.md>"

   Path A（来自 tech-doc）：
   python3 {start_py} \\
     --project-root "$(pwd)" \\
     --conversation-id "<uuid>" \\
     --mode task-from-tech \\
     --tech-ref "<abs-path-to-tech-doc.md>"
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
