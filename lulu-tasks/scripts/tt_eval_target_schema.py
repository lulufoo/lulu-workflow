#!/usr/bin/env python3
"""Render work-order-eval-target.md from the active work-order round, and split it back."""

from __future__ import annotations

import re
from pathlib import Path

EVAL_TARGET_FILENAME = "work-order-eval-target.md"
TECH_DOC_CHAPTER = "tech-doc"
TASK_LIST_CHAPTER = "task-list"
TASK_CHAPTER_PREFIX = "task-"
_CHAPTER_MARKER = re.compile(r"^<!-- chapter:([A-Za-z0-9_-]+) -->[ \t]*$", re.MULTILINE)


def eval_target_path(session_dir: Path) -> Path:
    return session_dir / "eval" / EVAL_TARGET_FILENAME


def task_file_for_chapter(session_dir: Path, chapter_id: str) -> Path:
    return session_dir / "tasks" / chapter_id[len(TASK_CHAPTER_PREFIX):] / "task.md"


def _chapter(chapter_id: str, body: str) -> str:
    return f"<!-- chapter:{chapter_id} -->\n\n{body.strip()}\n"


def split_eval_target(text: str) -> dict[str, str]:
    """Return chapter_id -> stripped body, in document order. Inverse of render."""
    markers = list(_CHAPTER_MARKER.finditer(text))
    if not markers:
        raise ValueError("eval target has no chapter markers")
    if text[: markers[0].start()].strip():
        raise ValueError("eval target has content before the first chapter marker")
    chapters: dict[str, str] = {}
    for index, marker in enumerate(markers):
        chapter_id = marker.group(1)
        if chapter_id in chapters:
            raise ValueError(f"duplicate chapter: {chapter_id}")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        chapters[chapter_id] = text[marker.end():end].strip()
    return chapters


def render_eval_target(session_dir: Path, *, tech_ref: str) -> str:
    task_list = session_dir / "task-list.md"
    if not task_list.is_file():
        raise FileNotFoundError(f"task-list.md missing: {task_list}")
    tech_path = Path(tech_ref)
    if not tech_ref or not tech_path.is_file():
        raise FileNotFoundError(f"tech-doc missing: {tech_ref}")
    parts = [
        _chapter("tech-doc", tech_path.read_text(encoding="utf-8")),
        _chapter("task-list", task_list.read_text(encoding="utf-8")),
    ]
    tasks_dir = session_dir / "tasks"
    if tasks_dir.is_dir():
        for task_md in sorted(tasks_dir.glob("t*/task.md")):
            parts.append(
                _chapter(
                    f"task-{task_md.parent.name}",
                    task_md.read_text(encoding="utf-8"),
                )
            )
    return "\n".join(parts)


def render_and_save_eval_target(session_dir: Path, *, tech_ref: str) -> Path:
    out = eval_target_path(session_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_eval_target(session_dir, tech_ref=tech_ref), encoding="utf-8")
    return out
