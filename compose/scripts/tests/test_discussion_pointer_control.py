#!/usr/bin/env python3
"""Tests for discussion_pointer_control.py (multi-subdesign v1.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: E402
from discussion_pointer_control import (  # noqa: E402
    cmd_accept_l,
    cmd_can_admit,
    cmd_can_enter_evaluate,
    cmd_demote_acceptance,
    cmd_fix_l,
    cmd_mark_done,
    cmd_ready,
    cmd_resume,
    cmd_status,
    cmd_switch,
    main,
    stage_gate_for_revision,
)
from discussion_pointer_schema import (  # noqa: E402
    build_pointer_from_tree,
    load_discussion_pointer,
    save_discussion_pointer,
)

_PROFILE = "lulu-design"


def _set_focus_evaluating(rev: Path) -> None:
    ptr = load_discussion_pointer(rev)
    focus = ptr["focus"]
    cell = ptr["by_id"][focus]
    cell["intake"] = "done"
    cell["acceptance"] = "pending"
    cell["phase"] = "evaluating"
    save_discussion_pointer(rev, ptr)


def _seed_rev(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "Base", "summary": "a"},
            {"id": "L2", "title": "Dep", "summary": "b"},
            {"id": "L3", "title": "Sib", "summary": "c"},
        ],
        edges=[
            {"from": "L2", "to": "L1"},
            {"from": "L3", "to": "L1"},
        ],
        order=["L1", "L2", "L3"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    save_discussion_pointer(rev, build_pointer_from_tree(tree))
    return rev


def test_status_ok(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_status(rev) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["focus"] == "L1"
    assert out["active"] == ["L1"]
    assert "L1" in out["ready"]
    assert "L2" not in out["ready"]
    assert "pointer" not in out
    assert "frontier" not in out
    assert out["node_ids"] == ["L1", "L2", "L3"]


def test_resume_no_state_change(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    before = load_discussion_pointer(rev)
    assert cmd_resume(rev) == 0
    after = load_discussion_pointer(rev)
    assert after == before
    out = json.loads(capsys.readouterr().out)
    assert out["command"] == "resume"


def test_switch_enter_policy(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_switch(rev, target="L2", confirm=True, profile_id=_PROFILE) == 1
    assert load_discussion_pointer(rev)["focus"] == "L1"

    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    capsys.readouterr()
    assert cmd_ready(rev) == 0
    ready_out = json.loads(capsys.readouterr().out)
    assert set(ready_out["ready"]) >= {"L1", "L2", "L3"}

    assert cmd_switch(rev, target="L2", confirm=True, profile_id=_PROFILE) == 0
    ptr = load_discussion_pointer(rev)
    assert ptr["focus"] == "L2"
    assert set(ptr) == {"tree_ref", "focus", "by_id"}
    assert cmd_can_admit(rev, target="L3") == 0


def test_switch_without_confirm_rejected(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    assert cmd_switch(rev, target="L2", confirm=False, profile_id=_PROFILE) == 1
    assert load_discussion_pointer(rev)["focus"] == "L1"


def test_stage_gate_blocks_until_deps_acceptance_done(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    assert cmd_switch(rev, target="L2", confirm=True, profile_id=_PROFILE) == 0
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    assert cmd_can_enter_evaluate(rev, target="L2") == 1
    ok, reason = stage_gate_for_revision(rev)
    assert ok is False
    assert reason and "acceptance" in reason

    assert cmd_switch(rev, target="L1", confirm=True, profile_id=_PROFILE) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    _set_focus_evaluating(rev)
    assert cmd_mark_done(rev, confirm=True, kind="acceptance", profile_id=_PROFILE) == 0
    assert cmd_switch(rev, target="L2", confirm=True, profile_id=_PROFILE) == 0
    assert cmd_can_enter_evaluate(rev, target="L2") == 0
    ok2, _ = stage_gate_for_revision(rev)
    assert ok2 is True


def test_demote_acceptance(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    _set_focus_evaluating(rev)
    assert cmd_mark_done(rev, confirm=True, kind="acceptance", profile_id=_PROFILE) == 0
    assert cmd_demote_acceptance(
        rev, target="L1", confirm=True, profile_id=_PROFILE
    ) == 0
    ptr = load_discussion_pointer(rev)
    assert ptr["by_id"]["L1"]["acceptance"] == "pending"
    progress = (rev / "l-step-progress.md").read_text(encoding="utf-8")
    assert "FreeEdit" in progress


def test_removed_legacy_cli_unknown(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "--revision-dir",
                str(rev),
                "--profile",
                _PROFILE,
                "phase-switch",
                "--confirm",
            ]
        )
    with pytest.raises(SystemExit):
        main(
            [
                "--revision-dir",
                str(rev),
                "--profile",
                _PROFILE,
                "migrate",
                "--confirm",
            ]
        )


def test_acceptance_mark_done_requires_evaluating_and_boundary(
    tmp_path: Path, capsys
) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    capsys.readouterr()
    assert cmd_mark_done(rev, confirm=True, kind="acceptance", profile_id=_PROFILE) == 1
    err = json.loads(capsys.readouterr().err)
    assert "expected evaluating" in err["error"]
    assert "accept-l" in err["error"]

    _set_focus_evaluating(rev)
    doc.write_text("# L1\n\n", encoding="utf-8")
    assert cmd_mark_done(rev, confirm=True, kind="acceptance", profile_id=_PROFILE) == 1
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    assert cmd_mark_done(rev, confirm=True, kind="acceptance", profile_id=_PROFILE) == 0


def test_accept_l_and_fix_l(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True, kind="intake", profile_id=_PROFILE) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    ptr = load_discussion_pointer(rev)
    ptr["by_id"]["L1"]["phase"] = "evaluating"
    save_discussion_pointer(rev, ptr)

    assert cmd_fix_l(rev, confirm=True, profile_id=_PROFILE) == 0
    assert load_discussion_pointer(rev)["by_id"]["L1"]["phase"] == "in_progress"

    ptr = load_discussion_pointer(rev)
    ptr["by_id"]["L1"]["phase"] = "evaluating"
    save_discussion_pointer(rev, ptr)
    capsys.readouterr()
    assert cmd_accept_l(rev, confirm=True, switch=True, profile_id=_PROFILE) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["accepted"] == "L1"
    assert out["switched_to"] in ("L2", "L3")
    assert load_discussion_pointer(rev)["by_id"]["L1"]["phase"] == "accepted"
    assert load_discussion_pointer(rev)["by_id"]["L1"]["acceptance"] == "done"


def test_seam_report_advisory(tmp_path: Path, capsys) -> None:
    from discussion_pointer_control import cmd_seam_report

    rev = _seed_rev(tmp_path)
    assert cmd_seam_report(rev, profile_id=_PROFILE) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hard_reject"] is False
    assert out["edges_checked"] == 2


def test_control_module_lives_in_core() -> None:
    assert (CORE / "discussion_pointer_control.py").is_file()
