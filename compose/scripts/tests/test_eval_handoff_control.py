"""Tests for Compose EvalHandoff control (execution dir + lease publish)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from eval_handoff_control import commit_artifacts, request_handoff
from compose_eval_handoff_schema import build_artifact_manifest, validate_eval_handoff
from execution_state_schema import build_execution_state, save_execution_state
from init_working_helpers import (
    init_working_ready,
    mark_focus_evaluating,
    mark_focus_intake_done,
)
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
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
    (ws.parent / "execution" / "design-doc.md").write_text("# design\n", encoding="utf-8")
    return ws


def test_request_handoff_execution_paths(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    result = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    handoff = result["handoff"]
    assert validate_eval_handoff(handoff) == []
    context = handoff["context"]
    assert "focus_l" not in context
    assert "slice_dir" not in context
    assert context["evaluate_round"] == 1
    assert context["eval_run_id"]
    assert context["execution_fingerprint"]
    assert context["evaluate_state_path"].endswith("/execution/evaluate-state.md")
    assert context["evaluate_dir"].endswith("/execution/evaluate1")
    assert Path(context["write_staging_dir"]).is_dir()
    assert handoff["adapter"]["adapter_class"] == "ComposeEvalAdapter"


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
        execution_fingerprint_value=context["execution_fingerprint"],
        eval_run_id=context["eval_run_id"],
        evaluate_round=1,
        staged_relative_path=review_name,
        final_relative_path=review_name,
        artifact_digest=digest,
    )
    save_execution_state(ws.parent, build_execution_state("FreeEdit"))
    commit = commit_artifacts(
        _CYCLE, tmp_path, manifest=manifest, profile_id=_PROFILE
    )
    assert commit["ok"] is False
    assert "Evaluating" in commit["error"] or "stale" in commit["error"]
    assert not (ws.parent / "execution" / "evaluate1" / review_name).exists()


def test_done_round_does_not_reuse_evaluate_dir(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    first = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert first["ok"] is True, first
    c1 = first["handoff"]["context"]
    Path(c1["evaluate_dir"]).mkdir(parents=True, exist_ok=True)
    (Path(c1["evaluate_dir"]) / "design-review-e11.md").write_text(
        "# r1\n", encoding="utf-8"
    )
    Path(c1["evaluate_state_path"]).write_text(
        "---\nversion: 3\nphase: evaluate\neval_status: done\n"
        "evaluate_round: 1\nfix_phase: done\ndimension_dispatch: parallel\n"
        'dimension_status: {"x":"complete"}\n'
        'issue_counts: {"x":{"total":"0","resolved":"0"}}\n'
        "total_issues: 0\nresolved_issues: 0\n"
        "fix_severity: \nfix_severity_reason: \n---\n",
        encoding="utf-8",
    )
    second = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert second["ok"] is True, second
    c2 = second["handoff"]["context"]
    assert c2["evaluate_dir"].endswith("/execution/evaluate2")
    assert c1["evaluate_dir"] != c2["evaluate_dir"]
    assert (Path(c1["evaluate_dir"]) / "design-review-e11.md").is_file()
