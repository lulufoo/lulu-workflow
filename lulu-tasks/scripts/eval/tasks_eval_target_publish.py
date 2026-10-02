#!/usr/bin/env python3
"""Publish a remediated EvalTarget for lulu-tasks and split task chapters back.

Only `<!-- chapter:task-tN -->` bodies may change. A publication that touches
the tech-doc or task-list chapter, or adds or removes a task chapter, is
refused with a `tasks-scope-rejected:` reason so the parent can return the
work order to Drafting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
_EVAL_SCRIPTS = Path(__file__).resolve().parents[3] / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval_admission import file_digest
from tt_eval_runtime_schema import load_runtime, runtime_path
from tt_eval_target_schema import (
    TASK_CHAPTER_PREFIX,
    TASK_LIST_CHAPTER,
    TECH_DOC_CHAPTER,
    eval_target_path,
    split_eval_target,
    task_file_for_chapter,
)

SCOPE_REJECTED = "tasks-scope-rejected"


def _failure(error: str) -> dict[str, Any]:
    return {"ok": False, "error": error}


def _scope_error(session_dir: Path, live_text: str, new_text: str) -> str | None:
    try:
        live = split_eval_target(live_text)
        new = split_eval_target(new_text)
    except ValueError as exc:
        return f"{SCOPE_REJECTED}: {exc}"
    if set(new) != set(live):
        return f"{SCOPE_REJECTED}: chapters added or removed"
    for fixed in (TECH_DOC_CHAPTER, TASK_LIST_CHAPTER):
        if new.get(fixed) != live.get(fixed):
            return f"{SCOPE_REJECTED}: {fixed} chapter changed"
    for chapter_id in new:
        if chapter_id in (TECH_DOC_CHAPTER, TASK_LIST_CHAPTER):
            continue
        if not chapter_id.startswith(TASK_CHAPTER_PREFIX):
            return f"{SCOPE_REJECTED}: unknown chapter {chapter_id}"
        if not task_file_for_chapter(session_dir, chapter_id).is_file():
            return f"{SCOPE_REJECTED}: task file missing for {chapter_id}"
    return None


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _publish_composite(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    source_path: Path,
    expected_digest: str,
    lease_id: str,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    if not lease_id or lease_id != str(runtime.get("active_lease_id") or ""):
        return _failure("lease_id mismatch")
    staging = Path(str(runtime.get("write_staging_dir") or ""))
    source = Path(source_path).resolve()
    if not staging.is_dir() or not source.is_relative_to(staging.resolve()):
        return _failure("source is outside the active write staging dir")
    if not source.is_file():
        return _failure(f"source missing: {source}")
    target = eval_target_path(session_dir)
    if not target.is_file():
        return _failure(f"eval target missing: {target}")
    if file_digest(target) != expected_digest:
        return _failure("target digest mismatch")
    live_text = target.read_text(encoding="utf-8")
    new_bytes = source.read_bytes()
    new_text = new_bytes.decode("utf-8")
    scope_error = _scope_error(session_dir, live_text, new_text)
    if scope_error:
        return _failure(scope_error)
    live = split_eval_target(live_text)
    changed: list[str] = []
    for chapter_id, body in split_eval_target(new_text).items():
        if chapter_id.startswith(TASK_CHAPTER_PREFIX) and body != live[chapter_id]:
            _write_atomic(task_file_for_chapter(session_dir, chapter_id), (body + "\n").encode("utf-8"))
            changed.append(chapter_id)
    _write_atomic(target, new_bytes)
    return {
        "ok": True,
        "target_path": target.resolve().as_posix(),
        "target_digest": file_digest(target),
        "changed_chapters": changed,
    }


def commit_eval_target(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    staged_target_path: Path,
    base_digest: str,
    lease_id: str,
) -> dict[str, Any]:
    return _publish_composite(
        adapter,
        cycle_id,
        project_root,
        source_path=staged_target_path,
        expected_digest=base_digest,
        lease_id=lease_id,
    )


def restore_eval_target(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    snapshot_path: Path,
    expected_current_digest: str,
    lease_id: str,
) -> dict[str, Any]:
    return _publish_composite(
        adapter,
        cycle_id,
        project_root,
        source_path=snapshot_path,
        expected_digest=expected_current_digest,
        lease_id=lease_id,
    )
