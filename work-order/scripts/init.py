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

WORK_ORDER_CONFIG_DEFAULTS = {
    "task_template_url": "",
    "tasklist_template_url": "",
    "twca_url": "",
    "woqa_url": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize work-order workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    config_path = project_root / CONFIG_PATH
    config = read_json(config_path, default={})
    if "work_order" not in config:
        config["work_order"] = WORK_ORDER_CONFIG_DEFAULTS
        write_json(config_path, config)
        config_note = f"已添加 work_order 配置区块到 {config_path.as_posix()}"
    else:
        config_note = f"work_order 配置区块已存在，跳过（{config_path.as_posix()}）"

    hooks_path = project_root / HOOKS_JSON_PATH
    hooks_payload = read_json(hooks_path, default={"version": 1, "hooks": {}})
    merged = merge_hook_entry(hooks_payload)
    write_json(hooks_path, merged)

    config_path_display = config_path.as_posix()
    start_py = Path(__file__).resolve().parent / "start.py"
    print(f"""
work-order workflow 初始化完成。

{config_note}
Hook 已注册：{HOOK_COMMAND}

下一步：
1. 检查 {config_path_display} 中的 work_order 区块，确认 URL 正确。
   - twca_url：Tech-WorkOrder Coverage Audit 框架文档 URL。
   - woqa_url：Work Order Quality Audit 框架文档 URL。
   - task_template_url / tasklist_template_url：施工单模板 URL（通常无需修改）。
2. 启动施工单，运行 start 命令：

   python3 {start_py} \\
     --project-root "$(pwd)" \\
     --conversation-id "<your-conversation-id>" \\
     --tech-ref "<absolute-path-to-tech-doc.md>"
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
