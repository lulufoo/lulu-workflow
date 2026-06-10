#!/usr/bin/env python3
"""Tests for code_task_list.py."""

from pathlib import Path

import pytest

from code_task_list import (
    all_done,
    assert_task_done,
    first_pending,
    next_pending_after,
    parse_tasks,
)


_SAMPLE = """\
---
source: work-order
total: 3
---

# Code Task List

- [ ] t1 · First task
- [x] t2 · Second task
- [ ] t3 · Third task
"""


def test_parse_tasks():
    tasks = parse_tasks(_SAMPLE)
    assert tasks == [
        {"id": "t1", "done": False},
        {"id": "t2", "done": True},
        {"id": "t3", "done": False},
    ]


def test_parse_tasks_ignores_non_task_lines():
    content = "- [ ] not-a-task\n- [ ] t1 · ok\n"
    assert parse_tasks(content) == [{"id": "t1", "done": False}]


def test_first_pending():
    tasks = parse_tasks(_SAMPLE)
    assert first_pending(tasks) == "t1"


def test_first_pending_all_done():
    content = "- [x] t1\n- [x] t2\n"
    assert first_pending(parse_tasks(content)) is None


def test_next_pending_after():
    tasks = parse_tasks(_SAMPLE)
    assert next_pending_after(tasks, "t1") == "t3"
    assert next_pending_after(tasks, "t2") == "t3"
    assert next_pending_after(tasks, "t3") is None


def test_all_done():
    assert all_done(parse_tasks("- [x] t1\n- [x] t2\n")) is True
    assert all_done(parse_tasks("- [x] t1\n- [ ] t2\n")) is False
    assert all_done([]) is False


def test_assert_task_done_ok(tmp_path: Path):
    path = tmp_path / "code-task-list.md"
    path.write_text("- [x] t1\n", encoding="utf-8")
    assert_task_done(path, "t1")


def test_assert_task_done_not_done(tmp_path: Path):
    path = tmp_path / "code-task-list.md"
    path.write_text("- [ ] t1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not marked done"):
        assert_task_done(path, "t1")


def test_assert_task_done_missing(tmp_path: Path):
    path = tmp_path / "code-task-list.md"
    path.write_text("- [x] t2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not found"):
        assert_task_done(path, "t1")
