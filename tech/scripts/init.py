#!/usr/bin/env python3

import argparse
from pathlib import Path

from workflow_common import (
    resolve_workflow_config_path,
    read_json,
    write_json,
)

TECH_DOC_CONFIG_DEFAULTS = {
    "tpt_url": "",
    "tpef_url": "",
    "ptc_url": "",
    "ac_url": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize tech-doc workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    # Update workflow-config.json: add tech-doc section if missing
    config_path = resolve_workflow_config_path(project_root)
    config = read_json(config_path, default={})
    if "tech" not in config:
        config["tech"] = TECH_DOC_CONFIG_DEFAULTS
        write_json(config_path, config)
        config_note = f"已添加 tech 配置区块到 {config_path.as_posix()}"
    else:
        config_note = f"tech 配置区块已存在，跳过（{config_path.as_posix()}）"

    config_path_display = config_path.as_posix()
    print(f"""
tech-doc workflow 初始化完成。

{config_note}

下一步：
1. 检查 {config_path_display} 中的 tech-doc 区块，确认 URL 正确。
   - ac_url：填写项目架构约束文档路径（可选）。
2. 启动第一个技术文档，运行 start 命令：

   python3 {Path(__file__).resolve()} --help
   python3 {Path(__file__).resolve().parent / 'start.py'} \\
     --project-root "$(pwd)" \\
     --conversation-id "<your-conversation-id>" \\
     --product-ref "<path-to-product-doc.md>"
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
