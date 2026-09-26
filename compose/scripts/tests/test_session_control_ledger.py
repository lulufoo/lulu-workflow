#!/usr/bin/env python3
"""Session-control tests on the single-execution spine."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401

from execution_control import run_command
from execution_state_schema import build_execution_state, save_execution_state
from init_working_helpers import mark_all_l_accepted, seed_tech_plan_session
from session_control import deliver, ready_for_delivery, return_to_working
from session_state_schema import load_session_state, save_session_state
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import session_state_path
from workflow_state_schema import load_workflow_state


_CYCLE = "feat-session-ctl"
_PROFILE = DEFAULT_COMPOSE_PROFILE_ID


def _doc(rev: Path) -> Path:
    path = rev / "execution" / "tech-doc.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Plan\n\nBody.\n", encoding="utf-8")
    return path


def test_execution_write_requires_holder_finalize(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    ss_path = tmp_path / session_state_path(_CYCLE, _PROFILE, tmp_path)
    existing = load_session_state(ss_path)
    save_session_state(
        ss_path,
        active_doc=int(existing["active_doc"]),
        profile_path=str(existing["profile_path"]),
        profile_digest=str(existing["profile_digest"]),
        start_id=str(existing["start_id"]),
        holder_finalized=False,
    )
    result = run_command("enter-fact-intake", _CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "holder_not_finalized"


def test_ready_rejects_incomplete_execution(tmp_path: Path) -> None:
    ws = seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    _doc(ws.parent)
    save_execution_state(ws.parent, build_execution_state("Writing"))
    result = ready_for_delivery(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert "Completed" in result["error"]


def test_ready_and_return(tmp_path: Path) -> None:
    ws = seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    rev = ws.parent
    _doc(rev)
    mark_all_l_accepted(rev)
    ready = ready_for_delivery(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert ready["ok"] is True, ready
    assert ready["current_state"] == "ReadyForDelivery"
    assert Path(ready["package_path"]).is_file()

    back = return_to_working(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=True)
    assert back["ok"] is True
    assert load_workflow_state(ws)["current_state"] == "Working"


def test_deliver_records_package_digest(tmp_path: Path) -> None:
    ws = seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    rev = ws.parent
    _doc(rev)
    mark_all_l_accepted(rev)
    ready = ready_for_delivery(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert ready["ok"] is True, ready
    delivered = deliver(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=True)
    assert delivered["ok"] is True, delivered
    assert delivered["current_state"] == "Delivered"
