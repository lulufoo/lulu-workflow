#!/usr/bin/env python3
"""Holder finalize locates the pending session; CLI has no identity locators."""

from __future__ import annotations

from pathlib import Path

from argparse import Namespace

import bootstrap  # noqa: F401
import pytest

from holder_finalize_control import finalize_holder, main
from init_working_helpers import seed_tech_plan_session
from session_state_schema import load_session_state, save_session_state
from start import run_start
from cycle_schema import write_stage
from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, compose_profile_path
from workflow_profile_paths import session_state_path
from workflow_state_schema import save_workflow_state


_CYCLE = "feat-holder-finalize"
_PROFILE = DEFAULT_COMPOSE_PROFILE_ID


def _pending_start(tmp_path: Path) -> Path:
    ws = seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    save_workflow_state(ws, {"current_state": "Working"}, merge=True)
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
    return ss_path


def test_holder_finalize_reads_pending_session(tmp_path: Path) -> None:
    ss_path = _pending_start(tmp_path)
    result = finalize_holder(
        cycle_id=_CYCLE,
        project_root=tmp_path,
        confirm=True,
    )
    assert result["ok"] is True, result
    assert result["holder_finalized"] is True
    assert result["transitioned"] is True
    assert load_session_state(ss_path)["holder_finalized"] is True


def test_holder_finalize_stale_when_not_pending(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE)
    result = finalize_holder(
        cycle_id=_CYCLE,
        project_root=tmp_path,
        confirm=True,
    )
    assert result["ok"] is False
    assert result["code"] == "stale_holder_finalize"


def test_start_completes_pending_handshake(tmp_path: Path) -> None:
    ss_path = _pending_start(tmp_path)
    before = load_session_state(ss_path)
    write_stage(_CYCLE, _PROFILE, tmp_path / CACHE_DIR)
    scope = ss_path.parent / f"revision{before['active_doc']}" / "scope-package.json"
    result = run_start(
        Namespace(
            project_root=str(tmp_path),
            cycle_id=_CYCLE,
            profile_path=str(compose_profile_path(_PROFILE)),
            scope_package=str(scope),
            conversation_id="",
        )
    )
    assert result["ok"] is True, result
    assert result["holder_finalized"] is True
    after = load_session_state(ss_path)
    assert after["holder_finalized"] is True
    assert after["start_id"] == before["start_id"]
    assert after["active_doc"] == before["active_doc"]
    assert not (ss_path.parent / f"revision{int(before['active_doc']) + 1}").exists()


def test_holder_finalize_cli_rejects_identity_flags(tmp_path: Path) -> None:
    _pending_start(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "--project-root",
                str(tmp_path),
                "--cycle-id",
                _CYCLE,
                "--start-id",
                "x",
                "--confirm",
            ]
        )
