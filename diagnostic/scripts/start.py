#!/usr/bin/env python3

import argparse
from pathlib import Path

from archive import run as run_archive
from workflow_common import session_state_path, write_session_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a diagnostic workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--feature-id", required=True, help="Feature ID (from feature_init.py).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    feature_id = args.feature_id.strip()

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=feature_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    ss_path = project_root / session_state_path(feature_id)
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
