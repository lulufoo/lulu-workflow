#!/usr/bin/env python3

import argparse
from pathlib import Path

from archive import run as run_archive
from workflow_common import (
    read_md_field,
    session_state_path,
    state_path,
    write_md_state,
    write_session_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new product doc workflow session.")
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
    if ss_path.exists():
        try:
            active_doc = int(read_md_field(ss_path, "active_doc", default="0")) + 1
        except ValueError:
            active_doc = 1
    else:
        active_doc = 1

    write_session_state(ss_path, active_doc)

    ws_path = project_root / state_path(feature_id, active_doc)
    write_md_state(ws_path, "Drafting", evaluate_round=0)

    print(f"""
会话已启动。

会话状态文件：{ss_path.as_posix()}
当前产品文档：revision{active_doc}
状态文件：{ws_path.as_posix()}
当前状态：Drafting
评估轮次：0

工作流已就绪，可以开始产品文档起草。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
