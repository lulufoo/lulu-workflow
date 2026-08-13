"""Tests for Compose EvalHandoff control (per-L paths + lease publish)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
from l_ledger_schema import build_ledger, load_l_ledger, save_l_ledger
from scope_package_schema import build_scope_package, save_scope_package, write_source_path_mirrors
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
    assert context["eval_run_id"]
    assert context["ledger_fingerprint"]
    assert context["evaluate_state_path"].endswith("/L1/evaluate-state.md")
    assert context["evaluate_dir"].endswith("/L1/evaluate1")
    assert Path(context["write_staging_dir"]).is_dir()
    assert handoff["adapter"]["adapter_class"] == "TechDesignEvalAdapter"
    assert eval_layout_for_revision(ws.parent) == "per-l"


def test_multi_l_rounds_do_not_collide(tmp_path: Path) -> None:
    ws = _seed_session(tmp_path)
    rev = ws.parent
    src = tmp_path / "scope-src.md"
    src.write_text("# scope\n", encoding="utf-8")
    package = build_scope_package(
        [
            {"id": "L1", "title": "One", "source_path": str(src.resolve())},
            {"id": "L2", "title": "Two", "source_path": str(src.resolve())},
        ]
    )
    save_scope_package(rev, package)
    write_source_path_mirrors(rev, package)
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Evaluating"
    save_l_ledger(rev, ledger)
    mark_focus_evaluating(rev)
    (rev / "L1").mkdir(exist_ok=True)
    (rev / "L2").mkdir(exist_ok=True)
    (rev / "L1" / "design-doc.md").write_text("# L1\n", encoding="utf-8")
    (rev / "L2" / "design-doc.md").write_text("# L2\n", encoding="utf-8")

    h1 = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert h1["ok"] is True, h1
    c1 = h1["handoff"]["context"]
    assert c1["evaluate_dir"].endswith("/L1/evaluate1")
    Path(c1["evaluate_dir"]).mkdir(parents=True, exist_ok=True)
    (Path(c1["evaluate_dir"]) / "design-review-e11.md").write_text("# r1\n", encoding="utf-8")
    Path(c1["evaluate_state_path"]).write_text(
        "---\nversion: 3\nphase: evaluate\neval_status: done\n"
        "evaluate_round: 1\nfix_phase: done\ndimension_dispatch: parallel\n"
        'dimension_status: {"x":"complete"}\n'
        'issue_counts: {"x":{"total":"0","resolved":"0"}}\n'
        "total_issues: 0\nresolved_issues: 0\n"
        "fix_severity: \nfix_severity_reason: \n---\n",
        encoding="utf-8",
    )

    ledger = load_l_ledger(rev)
    ledger["focus"] = "L2"
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["state"] = "Evaluating"
    save_l_ledger(rev, ledger)
    mark_focus_evaluating(rev)

    h2 = request_handoff(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert h2["ok"] is True, h2
    c2 = h2["handoff"]["context"]
    assert c2["evaluate_dir"].endswith("/L2/evaluate1")
    assert c2["evaluate_state_path"].endswith("/L2/evaluate-state.md")
    assert (rev / "L1" / "evaluate1" / "design-review-e11.md").is_file()
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
        ledger_fingerprint_value=context["ledger_fingerprint"],
        eval_run_id=context["eval_run_id"],
        focus_l="L1",
        evaluate_round=1,
        staged_relative_path=review_name,
        final_relative_path=review_name,
        artifact_digest=digest,
    )

    ledger = load_l_ledger(ws.parent)
    ledger["by_id"]["L1"]["state"] = "FreeEdit"
    save_l_ledger(ws.parent, ledger)

    commit = commit_artifacts(
        _CYCLE, tmp_path, manifest=manifest, profile_id=_PROFILE
    )
    assert commit["ok"] is False
    assert "Evaluating" in commit["error"] or "stale" in commit["error"]
    assert not (ws.parent / "L1" / "evaluate1" / review_name).exists()
