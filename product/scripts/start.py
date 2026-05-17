#!/usr/bin/env python3

import argparse
from pathlib import Path

from workflow_common import state_path, write_md_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new product doc workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--conversation-id", required=True, help="Current Cursor conversation ID.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    conv_id = args.conversation_id.strip()

    s_path = project_root / state_path(conv_id)
    write_md_state(s_path, "Drafting")

    print(f"""
会话已启动。

状态文件：{s_path.as_posix()}
当前状态：Drafting

工作流已就绪，可以开始产品文档起草。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
