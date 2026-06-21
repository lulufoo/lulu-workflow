#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from subagent_config import ensure_platform_config  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import gitignore_entry  # noqa: E402

from ta_workflow_common import (  # noqa: E402
    SKILL_ROOT,
    resolve_workflow_config_path,
)

_PLATFORM = detect_platform()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize lulu-dev-workflow in a project.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    return parser.parse_args()


def ensure_gitignore_entry(project_root: Path) -> None:
    entry = gitignore_entry(_PLATFORM)
    if entry is None:
        return
    gitignore_path = project_root / ".gitignore"
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

    ensure_platform_config(project_root, platform=_PLATFORM)
    ensure_gitignore_entry(project_root)

    config_path = resolve_workflow_config_path(project_root)
    config_path_display = config_path.as_posix()
    if config_path.exists():
        config_note = f"workflow-config 已存在：{config_path_display}"
    else:
        config_note = (
            f"workflow-config 未配置。请运行 lulu-dev-workflow configure "
            f"（目标路径：{config_path_display}）"
        )

    _start_py = str(SKILL_ROOT / "scripts" / "start.py").replace(str(Path.home()), "~")
    print(f"""
tech-arch 初始化完成。

{config_note}

下一步：
1. 若尚未 configure，先应用 workflow-config.json。
2. 开始第一个技术架构文档，运行 start 命令：

   python3 {_start_py} \\
     --project-root "$(pwd)" --cycle-id "<your-cycle-id>"
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
