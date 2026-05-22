#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from workflow_common import (
    PLATFORM_CONFIG_PATH,
    SKILL_ROOT,
    resolve_workflow_config_path,
    read_json,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize lulu-dev-workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_template_payload(template_name: str) -> dict:
    template_path = source_root() / "templates" / template_name
    with template_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_gitignore_entry(project_root: Path) -> None:
    gitignore_path = project_root / ".gitignore"
    entry = ".cursor"
    if not gitignore_path.exists():
        gitignore_path.write_text(f"{entry}\n", encoding="utf-8")
        return
    existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    if entry not in existing_lines:
        with gitignore_path.open("a", encoding="utf-8") as handle:
            if existing_lines:
                handle.write("\n")
            handle.write(f"{entry}\n")


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    config_template = load_template_payload("workflow-config.template.json")
    config_path = resolve_workflow_config_path(project_root)

    if config_path.exists():
        existing = read_json(config_path)
        existing["version"] = config_template["version"]
        config = existing
    else:
        config = config_template

    write_json(config_path, config)

    # Ensure platform config.json exists (Cursor)
    platform_cfg_path = project_root / PLATFORM_CONFIG_PATH
    if not platform_cfg_path.exists():
        write_json(platform_cfg_path, {
            "version": 1,
            "workflowConfig": "skill-config/lulu-dev-workflow/workflow-config.json",
        })

    ensure_gitignore_entry(project_root)

    config_path_display = config_path.as_posix()
    _start_py = str(SKILL_ROOT / "scripts" / "start.py").replace(str(Path.home()), "~")
    print(f"""
初始化完成。

创建的文件：
  {config_path_display}

下一步：
1. 编辑 {config_path_display}，填写 product 配置 URL。
2. 开始第一个产品文档，运行 start 命令：

   python3 {_start_py} \\
     --project-root "$(pwd)" --conversation-id "<your-conversation-id>"

配置模板参考：
  https://github.com/lulufoo/ai-software-dev/tree/main/ai-dev-workflow-framework/product_template
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
