#!/usr/bin/env python3
"""Workflow control: transitions, stdin persistence, frontmatter-only task checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tt_session_schema import write_session_state, session_file  # noqa: E402
from tt_workflow_common import CACHE_DIR, CACHE_SUBDIR  # noqa: E402
from tt_workflow_control import (  # noqa: E402
    cmd_apply_eval_disposition,
    cmd_deliver,
    cmd_enter_evaluating,
    cmd_put_task,
    cmd_resolve_context,
)
from tt_workflow_schema import read_workflow_state, workflow_file, write_workflow_state  # noqa: E402

_TASK = """---
version: 1
task_id: t1
title: Return ok
kind: coding
target_files:
  - a.py
dependencies: []
tdd_exempt: false
target_repo: lulu-workflow
execution_worktree: feature_worktree
exit_contract:
  commit: required
  commit_ref_md: required
  code_log: required
---

## Section 2: Function Specs
Function name: run
"""


def _emit(fn, *args, **kwargs) -> dict:
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kwargs)
    payload = json.loads(buf.getvalue())
    assert code == (0 if payload.get("ok") else 1)
    return payload


def _seed(project_root: Path, cycle_id: str, *, state: str = "Drafting", evaluate_round: int = 0) -> Path:
    tech = project_root / "plan.md"
    tech.write_text("# Plan\n", encoding="utf-8")
    write_session_state(session_file(project_root, cycle_id), 1)
    doc = project_root / CACHE_DIR / cycle_id / CACHE_SUBDIR / "r1"
    write_workflow_state(
        workflow_file(project_root, cycle_id, 1),
        current_state=state,
        evaluate_round=evaluate_round,
        tech_ref=tech.resolve().as_posix(),
    )
    return doc


def test_enter_evaluating_only_from_drafting(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-enter"
    _seed(tmp_path, cycle_id)
    entered = _emit(cmd_enter_evaluating, tmp_path, cycle_id)
    assert entered["current_state"] == "Evaluating"
    assert entered["evaluate_round"] == 1
    refused = _emit(cmd_enter_evaluating, tmp_path, cycle_id)
    assert refused["ok"] is False
    state = read_workflow_state(workflow_file(tmp_path, cycle_id, 1))
    assert state["evaluate_round"] == 1


def test_ready_then_deliver_and_drafting_does_not_deliver(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-ready"
    doc = _seed(tmp_path, cycle_id, state="Evaluating", evaluate_round=1)
    ready = _emit(
        cmd_apply_eval_disposition,
        tmp_path,
        cycle_id,
        {"ok": True, "disposition": "ready", "issues": []},
    )
    assert ready["current_state"] == "ReadyForDelivery"
    (doc / "tasks" / "t1").mkdir(parents=True)
    (doc / "tasks" / "t1" / "task.md").write_text(_TASK, encoding="utf-8")
    delivered = _emit(cmd_deliver, tmp_path, cycle_id)
    assert delivered["current_state"] == "Delivered"
    assert delivered["task_count"] == 1
    assert (doc / "human-delivery-gate.md").is_file()

    other = "tasks-flow-early"
    _seed(tmp_path, other, state="Drafting")
    blocked = _emit(cmd_deliver, tmp_path, other)
    assert blocked["ok"] is False
    assert read_workflow_state(workflow_file(tmp_path, other, 1))["current_state"] == "Drafting"
    assert not (tmp_path / CACHE_DIR / other / CACHE_SUBDIR / "r1" / "human-delivery-gate.md").exists()


def test_continue_does_not_change_state_and_drafting_disposition_does(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-disp"
    _seed(tmp_path, cycle_id, state="Evaluating", evaluate_round=2)
    kept = _emit(
        cmd_apply_eval_disposition,
        tmp_path,
        cycle_id,
        {"ok": True, "disposition": "continue", "next_phase": "compliance-crosscheck"},
    )
    assert kept["next_phase"] == "compliance-crosscheck"
    assert read_workflow_state(workflow_file(tmp_path, cycle_id, 1))["current_state"] == "Evaluating"
    drafted = _emit(
        cmd_apply_eval_disposition,
        tmp_path,
        cycle_id,
        {"ok": True, "disposition": "drafting", "issues": [{"task_id": "t1"}]},
    )
    assert drafted["current_state"] == "Drafting"
    ctx = _emit(cmd_resolve_context, tmp_path, cycle_id)
    assert ctx["unit"] == "drafting"
    assert ctx["evaluate_round"] == 2


def test_put_task_checks_frontmatter_not_section_order(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-task"
    _seed(tmp_path, cycle_id)
    stored = _emit(cmd_put_task, tmp_path, cycle_id, _TASK)
    assert stored["ok"] is True
    missing = _TASK.replace("target_repo: lulu-workflow\n", "")
    refused = _emit(cmd_put_task, tmp_path, cycle_id, missing)
    assert refused["ok"] is False
    assert "target_repo" in refused["error"]
    no_kind = _TASK.replace("kind: coding\n", "")
    refused_kind = _emit(cmd_put_task, tmp_path, cycle_id, no_kind)
    assert refused_kind["ok"] is False
    assert "kind" in refused_kind["error"]
    bad_kind = _TASK.replace("kind: coding\n", "kind: other\n")
    refused_other = _emit(cmd_put_task, tmp_path, cycle_id, bad_kind)
    assert refused_other["ok"] is False
    assert "coding or action" in refused_other["error"]
    retired = _TASK.replace("kind: coding\n", "kind: verify\n")
    refused_verify = _emit(cmd_put_task, tmp_path, cycle_id, retired)
    assert refused_verify["ok"] is False
    assert "coding or action" in refused_verify["error"]


_ACTION = """---
version: 1
task_id: t2
title: Todos are migrated to Linear
kind: action
target_files: []
dependencies: []
effects: mutates
mutates: [linear]
exit_contract:
  receipt: required
---
# t2
"""


def test_put_task_accepts_action_without_worktree(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-action"
    _seed(tmp_path, cycle_id)
    assert _emit(cmd_put_task, tmp_path, cycle_id, _ACTION)["ok"] is True
    read_only = _ACTION.replace("effects: mutates\nmutates: [linear]\n", "effects: read_only\n")
    assert _emit(cmd_put_task, tmp_path, cycle_id, read_only)["ok"] is True


def test_put_task_refuses_bad_action_declarations(tmp_path: Path) -> None:
    cycle_id = "tasks-flow-action-bad"
    _seed(tmp_path, cycle_id)
    cases = {
        "missing effects": (
            _ACTION.replace("effects: mutates\nmutates: [linear]\n", ""),
            "missing effects",
        ),
        "unknown effects": (_ACTION.replace("effects: mutates", "effects: writes"), "read_only or mutates"),
        "mutates without targets": (_ACTION.replace("mutates: [linear]\n", ""), "non-empty mutates list"),
        "mutates with empty targets": (_ACTION.replace("[linear]", "[]"), "non-empty mutates list"),
        "read_only with targets": (
            _ACTION.replace("effects: mutates", "effects: read_only"),
            "must not declare mutates",
        ),
        "coding exit contract": (
            _ACTION.replace("  receipt: required\n", "  commit: required\n"),
            "exit_contract.receipt",
        ),
        "worktree without repo": (
            _ACTION.replace("dependencies: []\n", "dependencies: []\nexecution_worktree: feature_worktree\n"),
            "target_repo",
        ),
    }
    for name, (body, expected) in cases.items():
        refused = _emit(cmd_put_task, tmp_path, cycle_id, body)
        assert refused["ok"] is False, name
        assert expected in refused["error"], name
