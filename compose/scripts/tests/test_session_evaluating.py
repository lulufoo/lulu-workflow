#!/usr/bin/env python3
"""Tests for enter_evaluating_state (compose only, no eval init)."""

from __future__ import annotations

import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

sys.path.insert(0, str(CORE))
from session_evaluating import enter_evaluating_state  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    init_compose_session,
    load_workflow_state,
    save_workflow_state,
)
from discussion_pointer_schema import load_discussion_pointer  # noqa: E402
from init_working_helpers import (  # noqa: E402
    init_working_ready,
    mark_focus_intake_done,
)

_CYCLE = "feat-eval-state"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, DEFAULT_COMPOSE_PROFILE_ID)
    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True, exist_ok=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    ws = base / "revision1" / "workflow-state.md"
    return ws


def test_working_to_focus_evaluating(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_working_ready(ws, mode="tech")
    mark_focus_intake_done(ws.parent)

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is True
    assert result["transitioned"] is True
    assert result["evaluate_round"] == 1
    assert result["current_state"] == "Working"
    assert result["phase"] == "evaluating"
    loaded = load_workflow_state(ws)
    assert loaded["current_state"] == "Working"
    ptr = load_discussion_pointer(ws.parent)
    assert ptr["by_id"][ptr["focus"]]["phase"] == "evaluating"
    assert not (ws.parent / "evaluate-state.md").exists()


def test_idempotent_when_already_evaluating(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_working_ready(ws, mode="tech")
    mark_focus_intake_done(ws.parent)
    enter_evaluating_state(_CYCLE, tmp_path)

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is True
    assert result["transitioned"] is False
    assert result["evaluate_round"] == 1
    assert result["current_state"] == "Working"


def test_rejects_non_working(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_working_ready(ws, mode="tech")
    save_workflow_state(ws, {"current_state": "ReadyForDelivery"})

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is False
    assert result["current_state"] == "ReadyForDelivery"


def test_rejects_without_topology_is_blocking(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_compose_session(ws, mode="tech")
    save_workflow_state(ws, {"current_state": "Working"})

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is False
    action = (result.get("resume") or {}).get("action", "")
    assert "Blocking" in action
    assert "新开 revision" in action
    assert "补 lock" not in action
    assert "回到 Split" not in action


def test_rejects_when_intake_not_done(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_working_ready(ws, mode="tech")

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is False
    assert "intake" in (result.get("error") or "").lower()
    assert load_workflow_state(ws)["current_state"] == "Working"


def test_stage_gate_blocks_multi_l_when_deps_not_acceptance_done(tmp_path: Path) -> None:
    from dependency_tree_schema import build_tree, save_dependency_tree
    from discussion_pointer_schema import build_pointer_from_tree, save_discussion_pointer
    from slice_rulers_schema import build_slice_rulers, save_slice_rulers

    ws = _seed_session(tmp_path)
    init_working_ready(ws, mode="tech")
    rev = ws.parent
    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "Base", "summary": "a"},
            {"id": "L2", "title": "Dep", "summary": "b"},
        ],
        edges=[{"from": "L2", "to": "L1"}],
        order=["L1", "L2"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    rulers = build_slice_rulers(
        cut_axis="tech_domain",
        status="locked",
        rulers={
            "L1": {
                "id": "L1",
                "job": "base",
                "in": ["scope"],
                "out": ["x"],
                "seam": [{"with": "L2", "owns": "full_plan", "note": "n"}],
                "plan_checklist": ["c"],
            },
            "L2": {
                "id": "L2",
                "job": "dep",
                "in": ["x"],
                "out": ["ui"],
                "seam": [{"with": "L1", "owns": "depend_only", "note": "n"}],
                "plan_checklist": ["c"],
            },
        },
    )
    save_slice_rulers(rev, rulers)
    ptr = build_pointer_from_tree(tree)
    ptr["focus"] = "L2"
    ptr["by_id"]["L1"]["intake"] = "done"
    ptr["by_id"]["L1"]["phase"] = "in_progress"
    ptr["by_id"]["L2"]["intake"] = "done"
    ptr["by_id"]["L2"]["phase"] = "in_progress"
    save_discussion_pointer(rev, ptr, tree=tree)

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is False
    assert "StageGate" in (result.get("error") or result.get("resume", {}).get("action", ""))
    assert load_workflow_state(ws)["current_state"] == "Working"
