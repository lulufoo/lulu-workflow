#!/usr/bin/env python3
"""Tests for enter_evaluating_state (compose-kernel only, no eval init)."""

from __future__ import annotations

import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

sys.path.insert(0, str(CORE))
from session_evaluating import enter_evaluating_state  # noqa: E402
from workflow_state_schema import init_drafting, load_workflow_state, save_workflow_state  # noqa: E402

_CYCLE = "feat-eval-state"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    ws = base / "revision1" / "workflow-state.md"
    return ws


def test_drafting_to_evaluating(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode="tech")

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is True
    assert result["transitioned"] is True
    assert result["evaluate_round"] == 1
    loaded = load_workflow_state(ws)
    assert loaded["current_state"] == "Evaluating"
    assert not (ws.parent / "evaluate-state.md").exists()


def test_idempotent_when_already_evaluating(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode="tech")
    enter_evaluating_state(_CYCLE, tmp_path)

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is True
    assert result["transitioned"] is False
    assert result["evaluate_round"] == 1


def test_rejects_non_drafting(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode="tech")
    save_workflow_state(ws, {"current_state": "ReadyForDelivery"})

    result = enter_evaluating_state(_CYCLE, tmp_path)

    assert result["ok"] is False
    assert result["current_state"] == "ReadyForDelivery"
