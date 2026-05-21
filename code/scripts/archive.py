#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

from workflow_common import (
    archive_code_dir,
    code_hot_root,
    is_conv_completed,
    list_code_conv_ids,
    session_base_dir,
)


def restore_current_if_needed(
    project_root: Path,
    current_conv_id: str,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    hot_dir = project_root / session_base_dir(current_conv_id)
    cold_dir = project_root / archive_code_dir(current_conv_id)

    if hot_dir.exists():
        return True, ""
    if not cold_dir.exists():
        return True, ""

    msg = f"restore: {cold_dir.as_posix()} -> {hot_dir.as_posix()}"
    print(msg)
    if dry_run:
        return True, msg

    hot_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(cold_dir), str(hot_dir))
    except OSError as exc:
        print(f"错误：restore 失败：{exc}", file=sys.stderr)
        return False, msg

    archive_parent = cold_dir.parent
    if archive_parent.exists() and not any(archive_parent.iterdir()):
        archive_parent.rmdir()
    return True, msg


def archive_completed_convs(
    project_root: Path,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> Tuple[bool, List[str]]:
    code_root = project_root / code_hot_root()
    messages: List[str] = []
    ok = True

    for conv_id in list_code_conv_ids(code_root):
        if conv_id == exclude_conv_id:
            continue

        hot_dir = code_root / conv_id
        cold_dir = project_root / archive_code_dir(conv_id)
        completed = is_conv_completed(hot_dir)

        if completed is None:
            msg = f"skip: {conv_id} — 无法读取 session-state 或 workflow-state"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        if completed is False:
            msg = f"skip: {conv_id} — active session 仍在 Executing"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        if cold_dir.exists():
            msg = f"skip: {conv_id} — 冷区已存在 {cold_dir.as_posix()}"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        msg = f"archive: {hot_dir.as_posix()} -> {cold_dir.as_posix()}"
        print(msg)
        messages.append(msg)

        if dry_run:
            continue

        cold_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(hot_dir), str(cold_dir))
        except OSError as exc:
            print(f"错误：archive 失败（{conv_id}）：{exc}", file=sys.stderr)
            ok = False

    return ok, messages


def run(
    project_root: Path,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> int:
    restored_ok, _ = restore_current_if_needed(project_root, exclude_conv_id, dry_run=dry_run)
    if not restored_ok:
        return 1

    archived_ok, _ = archive_completed_convs(
        project_root,
        exclude_conv_id,
        dry_run=dry_run,
    )
    if not archived_ok:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore current code conv from archive and move Completed convs to cold storage.",
    )
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument(
        "--exclude-conv-id",
        required=True,
        help="Current conversation ID (never archived; restored from cold if needed).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print restore/archive actions without modifying disk.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    return run(
        project_root,
        exclude_conv_id=args.exclude_conv_id.strip(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
