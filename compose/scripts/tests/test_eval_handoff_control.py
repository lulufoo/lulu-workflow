"""Tests for Compose EvalHandoff control (per-L paths + lease publish)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from discussion_pointer_schema import load_discussion_pointer, save_discussion_pointer
from dependency_tree_schema import load_dependency_tree
from eval_handoff_control import (
    commit_artifacts,
    request_handoff,
)
from eval_handoff_schema import build_artifact_manifest, validate_eval_handoff
from init_working_helpers import (
    init_working_ready,
    mark_focus_evaluating,
    mark_focus_intake_done,
)
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import (
    eval_layout_for_revision,
    state_path,
)
from workflow_state_schema import save_workflow_state


_CYCLE = "feature-eval-handoff-001"
_PROFILE = "lulu-design"


def _seed_session(tmp_path: Path) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    ws = tmp_path / state_path(_CYCLE, 1, _PROFILE, tmp_path)
    ws.parent.mkdir(parents=True, exist_ok=True)
    init_working_ready(ws, mode="tech")
    mark_focus_intake_done(ws.parent)
    mark_focus_evaluating(ws.parent)
    save_workflow_state(ws, {"evaluate_round": "1"})
    (ws.parent / "L1").mkdir(exist_ok=True)
    (ws.parent / "L1" / "design-doc.md").write_text("# L1\n", encoding="utf-8")
    return ws


def test_request_handoff_per_l_paths(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    result = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    handoff = result["handoff"]
    errors = validate_eval_handoff(handoff)
    assert errors == []
    context = handoff["context"]
    assert context["layout"] == "per-l"
    assert context["focus_l"] == "L1"
    assert context["evaluate_round"] == 1
    assert context["evaluate_state_path"].endswith("/L1/evaluate-state.md")
    assert context["evaluate_dir"].endswith("/L1/evaluate1")
    assert Path(context["write_staging_dir"]).is_dir()
    assert handoff["adapter"]["adapter_class"] == "TechDesignEvalAdapter"
    assert eval_layout_for_revision(ws.parent) == "per-l"


def test_legacy_root_layout_while_active(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    root_state = ws.parent / "evaluate-state.md"
    root_state.write_text(
        "---\nversion: 3\nphase: evaluate\neval_status: active\n"
        "fix_phase: probe\ndimension_dispatch: parallel\n"
        'dimension_status: {"x":"pending"}\n'
        'issue_counts: {"x":{"total":"0","resolved":"0"}}\n'
        "total_issues: 0\nresolved_issues: 0\n"
        "fix_severity: \nfix_severity_reason: \n---\n",
        encoding="utf-8",
    )
    assert eval_layout_for_revision(ws.parent) == "legacy-root"
    result = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    context = result["handoff"]["context"]
    assert context["layout"] == "legacy-root"
    assert context["evaluate_state_path"].endswith("/revision1/evaluate-state.md")
    assert "/L1/" not in context["evaluate_dir"]


def test_multi_l_rounds_do_not_collide(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    # Promote to multi-L locked tree (L1 + L2).
    from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: WPS433
    from discussion_pointer_schema import build_pointer_from_tree  # noqa: WPS433
    from slice_rulers_schema import build_slice_rulers, save_slice_rulers  # noqa: WPS433

    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "One", "summary": "a"},
            {"id": "L2", "title": "Two", "summary": "b"},
        ],
        edges=[],
        order=["L1", "L2"],
        status="locked",
    )
    save_dependency_tree(ws.parent, tree)
    rulers = build_slice_rulers(
        cut_axis="tech_domain",
        status="locked",
        rulers={
            "L1": {
                "id": "L1",
                "job": "one",
                "in": ["a"],
                "out": ["b"],
                "seam": [],
                "plan_checklist": ["c"],
            },
            "L2": {
                "id": "L2",
                "job": "two",
                "in": ["b"],
                "out": ["c"],
                "seam": [],
                "plan_checklist": ["c"],
            },
        },
    )
    save_slice_rulers(ws.parent, rulers)
    pointer = build_pointer_from_tree(tree)
    pointer["focus"] = "L1"
    pointer["by_id"]["L1"]["intake"] = "done"
    pointer["by_id"]["L1"]["phase"] = "evaluating"
    pointer["by_id"]["L2"]["intake"] = "done"
    pointer["by_id"]["L2"]["phase"] = "in_progress"
    save_discussion_pointer(ws.parent, pointer, tree=tree)
    (ws.parent / "L1").mkdir(exist_ok=True)
    (ws.parent / "L2").mkdir(exist_ok=True)
    (ws.parent / "L1" / "design-doc.md").write_text("# L1\n", encoding="utf-8")
    (ws.parent / "L2" / "design-doc.md").write_text("# L2\n", encoding="utf-8")

    h1 = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert h1["ok"] is True, h1
    c1 = h1["handoff"]["context"]
    assert c1["evaluate_dir"].endswith("/L1/evaluate1")
    (Path(c1["evaluate_dir"])).mkdir(parents=True, exist_ok=True)
    (Path(c1["evaluate_dir"]) / "design-review-e11.md").write_text("# r1\n", encoding="utf-8")
    (Path(c1["evaluate_state_path"])).write_text(
        "---\nversion: 3\nphase: evaluate\neval_status: done\n"
        "evaluate_round: 1\nfix_phase: done\ndimension_dispatch: parallel\n"
        'dimension_status: {"x":"complete"}\n'
        'issue_counts: {"x":{"total":"0","resolved":"0"}}\n'
        "total_issues: 0\nresolved_issues: 0\n"
        "fix_severity: \nfix_severity_reason: \n---\n",
        encoding="utf-8",
    )

    pointer = load_discussion_pointer(ws.parent)
    pointer["focus"] = "L2"
    pointer["by_id"]["L1"]["phase"] = "accepted"
    pointer["by_id"]["L1"]["acceptance"] = "done"
    pointer["by_id"]["L2"]["phase"] = "evaluating"
    save_discussion_pointer(ws.parent, pointer, tree=load_dependency_tree(ws.parent))

    h2 = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert h2["ok"] is True, h2
    c2 = h2["handoff"]["context"]
    assert c2["evaluate_dir"].endswith("/L2/evaluate1")
    assert c2["evaluate_state_path"].endswith("/L2/evaluate-state.md")
    assert (ws.parent / "L1" / "evaluate1" / "design-review-e11.md").is_file()
    assert c1["evaluate_dir"] != c2["evaluate_dir"]


def test_commit_rejects_after_leave_evaluating(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    result = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    context = result["handoff"]["context"]
    staging = Path(context["write_staging_dir"])
    review_name = "design-review-e11.md"
    staged = staging / review_name
    staged.write_text("# review\n", encoding="utf-8")
    digest = hashlib.sha256(staged.read_bytes()).hexdigest()
    manifest = build_artifact_manifest(
        lease_id=context["lease_id"],
        pointer_fingerprint_value=context["pointer_fingerprint"],
        focus_l="L1",
        evaluate_round=1,
        staged_relative_path=review_name,
        final_relative_path=review_name,
        artifact_digest=digest,
    )

    # Simulate Fix-L: leave evaluating after handoff issued.
    pointer = load_discussion_pointer(ws.parent)
    pointer["by_id"]["L1"]["phase"] = "in_progress"
    save_discussion_pointer(ws.parent, pointer, tree=load_dependency_tree(ws.parent))

    commit = commit_artifacts(
        _CYCLE, tmp_path, manifest=manifest, profile_id=_PROFILE
    )
    assert commit["ok"] is False
    assert "evaluating" in commit["error"] or "stale" in commit["error"]
    assert not (ws.parent / "L1" / "evaluate1" / review_name).exists()
