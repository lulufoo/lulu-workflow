#!/usr/bin/env python3

import argparse
from pathlib import Path

from archive import run as run_archive
from workflow_common import session_state_path, write_session_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a diagnostic workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--conversation-id", required=True, help="Current Cursor conversation ID.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    conv_id = args.conversation_id.strip()

    archive_rc = run_archive(project_root, exclude_conv_id=conv_id)
    if archive_rc != 0:
        return archive_rc

    ss_path = project_root / session_state_path(conv_id)
    write_session_state(ss_path, "InProgress")

    print(f"""
诊断会话已启动。

会话状态文件：{ss_path.as_posix()}
当前状态：InProgress

工作流已就绪，可以开始 DDF 节点执行。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
