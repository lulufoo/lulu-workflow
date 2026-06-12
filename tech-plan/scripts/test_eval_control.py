#!/usr/bin/env python3
"""Tests for eval_control.py."""

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_control import (  # noqa: E402
    begin_artifact_remediation,
    begin_dimension,
    begin_eval_round,
    begin_sot_remediation,
    build_eval_loop_payload,
    check_artifact_remediation,
    check_dimension,
    check_sot_remediation,
    complete_round,
    compute_fix_severity,
    dispatch_list,
    finish_dimension_probe,
    init_round,
    probe_complete,
    resolve_execution_mode,
    resume_drafting,
)
from evaluate_state_schema import (  # noqa: E402
    init_evaluate_state,
    load_evaluate_state,
    merge_current_dimension,
    parse_current_dimension,
    save_evaluate_state,
    serialize_current_dimension,
)
from workflow_state_schema import (  # noqa: E402
    init_drafting,
    load_workflow_state,
    save_workflow_state,
)

_CYCLE = "feat-eval-control"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_SCRIPT = Path(__file__).resolve().parent / "eval_control.py"

_REVIEW_HEADER = (
    "# Tech Review — E2 | revision1 round 1\n\n"
    "**Date:** 2026-01-01\n"
    "**Refs:** codebase\n\n"
    "| ID | root_cause | sot_ref | location | severity | evidence "
    "| description | status | decision |\n"
    "|----|------------|---------|----------|----------|----------"
    "|-------------|--------|----------|\n"
)

_REVIEW_E2_PROBE = (
    _REVIEW_HEADER
    + "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | missing handling | "
    "missing error handling | pending | — |\n"
    + "| e2-2 | WO-ERROR | — | tech-doc §5 | minor | naming | "
    "naming inconsistency | pending | — |\n"
)

_REVIEW_E2_DONE = (
    _REVIEW_HEADER
    + "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | missing handling | "
    "missing error handling | fixed | fix |\n"
    + "| e2-2 | WO-ERROR | — | tech-doc §5 | minor | naming | "
    "naming inconsistency | ignored | ignore |\n"
)


def _seed_session(tmp_path: Path, *, active_doc: int = 1) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    return base / f"revision{active_doc}" / "workflow-state.md"


def _setup_evaluating(tmp_path: Path, *, mode: str = "product") -> Path:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode=mode, product_ref="/p.md" if mode == "product" else None)
    save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})
    init_evaluate_state(ws.parent / "evaluate-state.md", mode=mode)
    return ws


def _write_review(ws: Path, content: str, *, filename: str = "tech-review-e12.md") -> Path:
    eval_dir = ws.parent / "evaluate1"
    eval_dir.mkdir(parents=True, exist_ok=True)
    path = eval_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _setup_probed_e2(tmp_path: Path, *, mode: str = "product") -> Path:
    ws = _setup_evaluating(tmp_path, mode=mode)
    _write_review(ws, _REVIEW_E2_PROBE)
    finish_dimension_probe(_CYCLE, tmp_path, dim="e2")
    return ws


def _setup_complete_round_ready(
    tmp_path: Path,
    *,
    mode: str = "product",
) -> Path:
    ws = _setup_evaluating(tmp_path, mode=mode)
    dims = dispatch_list(mode)
    es_path = ws.parent / "evaluate-state.md"
    dim_map = {dim: "complete" for dim in dims}
    patch = {
        "current_dimension": serialize_current_dimension(dim_map),
        "fix_phase": "done",
        "e2_total_issues": "2",
        "e2_resolved_issues": "1",
        "total_issues": "2",
        "resolved_issues": "1",
    }
    save_evaluate_state(es_path, patch, merge=True)
    _write_review(ws, _REVIEW_E2_DONE)
    return ws


class TestDispatchList:
    def test_product_mode(self):
        assert dispatch_list("product") == ["e1", "e2", "e3"]

    def test_tech_mode(self):
        assert dispatch_list("tech") == ["e2", "e3"]


class TestInitRound:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        result = init_round(_CYCLE, tmp_path, mode="product")
        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["version"] == "2"
        assert es["eval_status"] == "active"
        assert es["fix_phase"] == "probe"
        dim_map = parse_current_dimension(es["current_dimension"])
        assert dim_map == {"e1": "pending", "e2": "pending", "e3": "pending"}

    def test_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        init_round(_CYCLE, tmp_path, mode="tech")
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = parse_current_dimension(es["current_dimension"])
        assert dim_map == {"e2": "pending", "e3": "pending"}


class TestBeginEvalRound:
    def test_from_drafting_enters_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["dispatch"] == ["e1", "e2", "e3"]

    def test_rejects_v1_evaluate_state(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        es_path = ws.parent / "evaluate-state.md"
        es_path.write_text(
            "---\nversion: 1\nphase: evaluate\ncurrent_dimension: e1\n"
            "e1_status: pending\ne1_total_issues: 0\ne1_resolved_issues: 0\n"
            "e2_status: pending\ne2_total_issues: 0\ne2_resolved_issues: 0\n"
            "e3_status: pending\ne3_total_issues: 0\ne3_resolved_issues: 0\n"
            "total_issues: 0\nresolved_issues: 0\nfix_severity: \"\"\n"
            "fix_severity_reason: \"\"\n---\n",
            encoding="utf-8",
        )
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "expected '2'" in result["reason"] or "not supported" in result["reason"]

    def test_re_evaluate_after_complete_round(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        complete_round(_CYCLE, tmp_path)
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["evaluate_round"] == 2
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["fix_phase"] == "probe"
        assert parse_current_dimension(es["current_dimension"])["e1"] == "pending"

    def test_rejects_re_evaluate_when_abandoned(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "abandoned" in result["reason"]


class TestBeginDimension:
    def test_marks_in_progress_and_returns_runner_input(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert parse_current_dimension(es["current_dimension"])["e2"] == "in_progress"
        assert result["runner_input"]["CYCLE_ID"] == _CYCLE
        assert "CYCLE_ID:" in result["dispatch_input"]


class TestFinishDimensionProbe:
    def test_happy_path(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        begin_dimension(_CYCLE, tmp_path, dim="e2")
        _write_review(ws, _REVIEW_E2_PROBE)
        result = finish_dimension_probe(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert result["outcome"] == "probed"
        assert result["total_issues"] == "2"
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert parse_current_dimension(es["current_dimension"])["e2"] == "probed"
        assert es["e2_total_issues"] == "2"

    def test_rejects_invalid_review(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        begin_dimension(_CYCLE, tmp_path, dim="e2")
        _write_review(ws, _REVIEW_HEADER + "| bad | row |\n")
        result = finish_dimension_probe(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is False

    def test_concurrent_finish_locked(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path, mode="tech")
        begin_dimension(_CYCLE, tmp_path, dim="e2")
        begin_dimension(_CYCLE, tmp_path, dim="e3")
        _write_review(ws, _REVIEW_E2_PROBE, filename="tech-review-e12.md")
        _write_review(
            ws,
            _REVIEW_HEADER + "| e3-1 | WO-ERROR | — | loc | minor | ev | d | pending | — |\n",
            filename="tech-review-e13.md",
        )
        errors: list[str] = []

        def _run(dim: str) -> None:
            try:
                finish_dimension_probe(_CYCLE, tmp_path, dim=dim)
            except ValueError as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=_run, args=("e2",))
        t2 = threading.Thread(target=_run, args=("e3",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert not errors
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = parse_current_dimension(es["current_dimension"])
        assert dim_map["e2"] == "probed"
        assert dim_map["e3"] == "probed"


class TestCheckDimension:
    def test_probed_outcome(self, tmp_path: Path):
        _setup_probed_e2(tmp_path)
        result = check_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert result["outcome"] == "probed"
        assert result["abandoned"] is False

    def test_fails_when_review_without_probed(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        begin_dimension(_CYCLE, tmp_path, dim="e2")
        _write_review(ws, _REVIEW_E2_PROBE)
        result = check_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is False
        assert "finish-dimension-probe" in result["reason"]

    def test_abandoned_outcome(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = check_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert result["abandoned"] is True


class TestProbeComplete:
    def test_advances_fix_phase(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path, mode="tech")
        for dim in ("e2", "e3"):
            begin_dimension(_CYCLE, tmp_path, dim=dim)
            fname = f"tech-review-e1{dim[-1]}.md"
            content = (
                _REVIEW_HEADER
                + f"| {dim}-1 | WO-ERROR | — | loc | minor | ev | desc | pending | — |\n"
            )
            _write_review(ws, content, filename=fname)
            finish_dimension_probe(_CYCLE, tmp_path, dim=dim)
        result = probe_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["fix_phase"] == "artifact-remediation"
        assert result["total_issues"] == "2"


class TestArtifactRemediation:
    def test_begin_skips_when_no_wo_pending(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(
            ws,
            _REVIEW_HEADER
            + "| e2-1 | SOT-DEFECT | product §1 | loc | medium | ev | desc "
            "| pending | — |\n",
        )
        for dim in ("e1", "e2", "e3"):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = merge_current_dimension(es, dim, "probed") if dim in dispatch_list("product") else es
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = begin_artifact_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["skip"] is True

    def test_check_advances_to_sot_remediation(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e11.md")
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e13.md")
        for dim in dispatch_list("product"):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = merge_current_dimension(es, dim, "probed")
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = check_artifact_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["fix_phase"] == "sot-remediation"

    def test_early_dim_complete_when_no_pending_sot(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e11.md")
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e13.md")
        for dim in dispatch_list("product"):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = merge_current_dimension(es, dim, "probed")
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        check_artifact_remediation(_CYCLE, tmp_path)
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = parse_current_dimension(es["current_dimension"])
        assert dim_map["e2"] == "complete"
        assert dim_map["e1"] == "complete"
        assert dim_map["e3"] == "complete"


class TestSotRemediation:
    def test_check_sets_abandoned_on_escalated(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "sot-remediation"},
        )
        _write_review(
            ws,
            _REVIEW_HEADER
            + "| e2-1 | SOT-DEFECT | product §1 | loc | critical | ev | desc "
            "| escalated | escalate |\n",
        )
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e11.md")
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e13.md")
        for dim in dispatch_list("product"):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = merge_current_dimension(es, dim, "probed")
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = check_sot_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["abandoned"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["eval_status"] == "abandoned"

    def test_all_dims_complete_after_check(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "sot-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e11.md")
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e13.md")
        for dim in dispatch_list("product"):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = merge_current_dimension(es, dim, "probed")
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = check_sot_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["abandoned"] is False
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = parse_current_dimension(es["current_dimension"])
        assert all(dim_map.get(dim) == "complete" for dim in dispatch_list("product"))


class TestCompleteRound:
    def test_writes_done_and_returns_summary(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        result = complete_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["eval_status"] == "done"
        assert result["fix_severity"] == "critical"
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["eval_status"] == "done"

    def test_rejects_if_fix_phase_not_done(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = complete_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "fix_phase" in result["reason"]


class TestComputeFixSeverity:
    def test_highest_severity_wins(self):
        issues = [
            {"id": "e2-1", "severity": "critical", "description": "x", "decision": "fix"},
            {"id": "e2-2", "severity": "minor", "description": "y", "decision": "ignore"},
        ]
        severity, reason = compute_fix_severity(issues)
        assert severity == "critical"


class TestResumeDrafting:
    def test_success_after_complete_round(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        complete_round(_CYCLE, tmp_path)
        result = resume_drafting(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert load_workflow_state(ws)["current_state"] == "Drafting"

    def test_failure_when_abandoned(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = resume_drafting(_CYCLE, tmp_path)
        assert result["ok"] is False


class TestResolveExecutionMode:
    def test_defaults_to_guided(self, tmp_path: Path):
        assert resolve_execution_mode(_CYCLE, tmp_path) == "guided"


class TestBuildEvalLoopPayload:
    def test_success(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        payload = build_eval_loop_payload(_CYCLE, tmp_path)
        assert payload["ok"] is True
        assert payload["dispatch"] == ["e1", "e2", "e3"]
