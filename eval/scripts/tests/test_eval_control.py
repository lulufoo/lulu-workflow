#!/usr/bin/env python3
"""Tests for eval/scripts/eval_control.py."""

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_TECH_PLAN_EVAL = _EVAL_SCRIPTS.parents[1] / "lulu-plan" / "scripts" / "eval"
_KERNEL_CORE = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "core"
_KERNEL_SCHEMA_SESSION = (
    _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "schema" / "session"
)
_KERNEL_TESTS = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "tests"
sys.path.insert(0, str(_KERNEL_CORE))
sys.path.insert(0, str(_KERNEL_SCHEMA_SESSION))
sys.path.insert(0, str(_KERNEL_TESTS))
sys.path.insert(0, str(_EVAL_SCRIPTS))
sys.path.insert(0, str(_TECH_PLAN_EVAL))

from tech_plan_eval_adapter import TechPlanEvalAdapter  # noqa: E402
import eval_control  # noqa: E402
from eval_control import (  # noqa: E402
    artifact_remediation_complete,
    begin_artifact_remediation,
    begin_dimension,
    begin_dimension_artifact_remediation,
    begin_dimension_sot_remediation,
    begin_eval_round,
    begin_sot_remediation,
    build_eval_loop_payload,
    check_artifact_remediation,
    check_dimension,
    check_dimension_artifact_remediation,
    check_dimension_sot_remediation,
    check_sot_remediation,
    collect_review_issues,
    complete_round,
    compute_fix_severity,
    dispatch_list,
    finish_dimension_probe,
    init_round,
    probe_complete,
    resolve_execution_mode,
    sot_remediation_complete,
)
from evaluate_state_ops import (  # noqa: E402
    dimension_status_legacy_map,
    init_evaluate_state_for_corpus,
    merge_current_dimension,
)
from evaluate_state_schema import (  # noqa: E402
    load_evaluate_state,
    parse_issue_counts,
    patch_issue_count,
    save_evaluate_state,
)
from session_control import resume_after_eval  # noqa: E402
from init_drafting_helpers import product_delivered_refs  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    init_drafting,
    load_workflow_state,
    save_workflow_state,
)

_CYCLE = "feat-eval-control"
from corpus_compose import COMPOSED_CORPUS_REF  # noqa: E402

_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_ADAPTER = TechPlanEvalAdapter()


def _corpus(cycle_id: str, tmp_path: Path):
    return _ADAPTER.resolve_eval_corpus(cycle_id, tmp_path)


def _init_evaluate_state(path: Path, *, cycle_id: str, tmp_path: Path) -> None:
    init_evaluate_state_for_corpus(
        path,
        _corpus(cycle_id, tmp_path),
        cycle_type="feature",
    )


@pytest.fixture(autouse=True)
def _set_eval_adapter():
    token = eval_control._ADAPTER_CTX.set(_ADAPTER)
    yield
    eval_control._ADAPTER_CTX.reset(token)

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
    from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-plan")
    return base / f"revision{active_doc}" / "workflow-state.md"


def _setup_evaluating(tmp_path: Path, *, mode: str = "product") -> Path:
    ws = _seed_session(tmp_path)
    init_drafting(
        ws,
        mode=mode,
        delivered_refs=product_delivered_refs("/p.md") if mode == "product" else [],
    )
    save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})
    _init_evaluate_state(ws.parent / "evaluate-state.md", cycle_id=_CYCLE, tmp_path=tmp_path)
    return ws


def _write_review(ws: Path, content: str, *, filename: str = "tech-review-e11.md") -> Path:
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


def _dim_map(es: dict, tmp_path: Path) -> dict[str, str]:
    return dimension_status_legacy_map(es, corpus=_corpus(_CYCLE, tmp_path))


def _merge_dim(es: dict, dim: str, status: str, tmp_path: Path) -> dict:
    return merge_current_dimension(
        es,
        dim,
        status,
        corpus=_corpus(_CYCLE, tmp_path),
    )


def _setup_complete_round_ready(
    tmp_path: Path,
    *,
    mode: str = "product",
) -> Path:
    ws = _setup_evaluating(tmp_path, mode=mode)
    dims = dispatch_list(_CYCLE, tmp_path)
    es_path = ws.parent / "evaluate-state.md"
    es = load_evaluate_state(es_path)
    merged = _merge_dim(es, dims[0], "complete", tmp_path)
    for dim in dims[1:]:
        merged = _merge_dim(merged, dim, "complete", tmp_path)
    merged["fix_phase"] = "done"
    merged = patch_issue_count(merged, "codebase-consistency", total="2", resolved="1")
    merged["total_issues"] = "2"
    merged["resolved_issues"] = "1"
    save_evaluate_state(es_path, merged, merge=False)
    _write_review(ws, _REVIEW_E2_DONE)
    return ws


class TestDispatchList:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", delivered_refs=product_delivered_refs("/p.md"))
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3"]

    def test_tech_mode_with_diagnostic_upstream(self, tmp_path: Path):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        ws = _seed_session(tmp_path)
        decision = tmp_path / "decision-doc.md"
        decision.write_text("# Decision\n", encoding="utf-8")
        refs = [DeliveredRef(type="lulu-approach", path=str(decision.resolve()))]
        init_drafting(ws, mode="tech", delivered_refs=refs)
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3", "e4"]

    def test_tech_mode_without_upstream(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3"]


class TestInitRound:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", delivered_refs=product_delivered_refs("/p.md"))
        result = init_round(_CYCLE, tmp_path, mode="product")
        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["version"] == "3"
        assert es["eval_status"] == "active"
        assert es["fix_phase"] == "probe"
        assert es["corpus_ref"] == COMPOSED_CORPUS_REF
        assert es.get("corpus_fingerprint")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map == {"e2": "pending", "e3": "pending"}

    def test_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        init_round(_CYCLE, tmp_path, mode="tech")
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map == {"e2": "pending", "e3": "pending"}

    def test_product_mode_without_delivered_refs_uses_base_dims(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", delivered_refs=[])
        init_round(_CYCLE, tmp_path, mode="product")
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert _dim_map(es, tmp_path) == {"e2": "pending", "e3": "pending"}


class TestBeginEvalRound:
    def test_from_drafting_enters_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", delivered_refs=product_delivered_refs("/p.md"))
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["dispatch"] == ["e2", "e3"]

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
        assert "not supported" in result["reason"] or "expected '3'" in result["reason"]

    def test_re_evaluate_after_complete_round(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        complete_round(_CYCLE, tmp_path)
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["evaluate_round"] == 2
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["fix_phase"] == "probe"
        assert _dim_map(es, tmp_path)["e2"] == "pending"

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
        assert _dim_map(es, tmp_path)["e2"] == "in_progress"
        ri = result["runner_input"]
        assert ri["CYCLE_ID"] == _CYCLE
        assert ri["DIMENSION_ID"] == "codebase-consistency"
        assert ri["DIMENSION"] == "e2"
        assert "SOTS_JSON" in ri
        sots = json.loads(ri["SOTS_JSON"])
        assert sots[0]["ref"] == {"root": ".", "strategy": "all"}
        assert "METHOD_JSON" in ri
        assert "EXECUTION_MODE" not in ri
        assert "EVAL_TARGET_PATH" in result["dispatch_input"]

    def test_accepts_canonical_dim_id(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="codebase-consistency")
        assert result["ok"] is True
        assert result["runner_input"]["DIMENSION_ID"] == "codebase-consistency"


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
        assert _dim_map(es, tmp_path)["e2"] == "probed"
        counts = parse_issue_counts(es["issue_counts"])
        assert counts["codebase-consistency"]["total"] == "2"

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
        _write_review(ws, _REVIEW_E2_PROBE, filename="tech-review-e11.md")
        _write_review(
            ws,
            _REVIEW_HEADER + "| e3-1 | WO-ERROR | — | loc | minor | ev | d | pending | — |\n",
            filename="tech-review-e12.md",
        )
        errors: list[str] = []

        def _run(dim: str) -> None:
            token = eval_control._ADAPTER_CTX.set(_ADAPTER)
            try:
                finish_dimension_probe(_CYCLE, tmp_path, dim=dim)
            except ValueError as exc:
                errors.append(str(exc))
            finally:
                eval_control._ADAPTER_CTX.reset(token)

        t1 = threading.Thread(target=_run, args=("e2",))
        t2 = threading.Thread(target=_run, args=("e3",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert not errors
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert _dim_map(es, tmp_path)["e2"] == "probed"
        assert _dim_map(es, tmp_path)["e3"] == "probed"


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
        review_files = {"e2": "tech-review-e11.md", "e3": "tech-review-e12.md"}
        for dim in ("e2", "e3"):
            begin_dimension(_CYCLE, tmp_path, dim=dim)
            content = (
                _REVIEW_HEADER
                + f"| {dim}-1 | WO-ERROR | — | loc | minor | ev | desc | pending | — |\n"
            )
            _write_review(ws, content, filename=review_files[dim])
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
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = begin_artifact_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["skip"] is True
        assert result["dispatch"] == []

    def test_begin_returns_dispatch_for_pending_wo(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_PROBE)
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = begin_artifact_remediation(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["skip"] is False
        assert "e2" in result["dispatch"]

    def test_per_dim_dispatch_input(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_PROBE)
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        es = _merge_dim(es, "e2", "probed", tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = begin_dimension_artifact_remediation(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert "REVIEW_OUTPUT_PATH" in result["dispatch_input"]
        assert "EXECUTION_MODE" not in result["dispatch_input"]

    def test_check_advances_to_sot_remediation(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e12.md")
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        for dim in dispatch_list(_CYCLE, tmp_path):
            check_dimension_artifact_remediation(_CYCLE, tmp_path, dim=dim)
        result = artifact_remediation_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["fix_phase"] == "sot-remediation"

    def test_early_dim_complete_when_no_pending_sot(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e12.md")
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        for dim in dispatch_list(_CYCLE, tmp_path):
            check_dimension_artifact_remediation(_CYCLE, tmp_path, dim=dim)
        check_artifact_remediation(_CYCLE, tmp_path)
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map["e2"] == "complete"
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
            filename="tech-review-e11.md",
        )
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e12.md")
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        result = check_dimension_sot_remediation(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert result["abandoned"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["eval_status"] == "abandoned"
        complete = sot_remediation_complete(_CYCLE, tmp_path)
        assert complete["ok"] is True
        assert complete["abandoned"] is True

    def test_all_dims_complete_after_check(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "sot-remediation"},
        )
        _write_review(ws, _REVIEW_E2_DONE)
        _write_review(ws, _REVIEW_HEADER, filename="tech-review-e12.md")
        for dim in dispatch_list(_CYCLE, tmp_path):
            es = load_evaluate_state(ws.parent / "evaluate-state.md")
            es = _merge_dim(es, dim, "probed", tmp_path)
            save_evaluate_state(ws.parent / "evaluate-state.md", es)
        for dim in dispatch_list(_CYCLE, tmp_path):
            check_dimension_sot_remediation(_CYCLE, tmp_path, dim=dim)
        result = sot_remediation_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["abandoned"] is False
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert all(
            _dim_map(es, tmp_path).get(dim) == "complete"
            for dim in dispatch_list(_CYCLE, tmp_path)
        )


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


class TestResumeAfterEval:
    def test_success_after_complete_round(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        complete_round(_CYCLE, tmp_path)
        result = resume_after_eval(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert load_workflow_state(ws)["current_state"] == "Drafting"

    def test_failure_when_abandoned(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = resume_after_eval(_CYCLE, tmp_path)
        assert result["ok"] is False


class TestResolveExecutionMode:
    def test_defaults_to_guided(self, tmp_path: Path):
        assert resolve_execution_mode(_CYCLE, tmp_path) == "guided"


class TestBuildEvalLoopPayload:
    def test_success(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        payload = build_eval_loop_payload(_CYCLE, tmp_path)
        assert payload["ok"] is True
        assert payload["dispatch"] == ["e2", "e3"]


class TestCollectReviewIssuesPrefix:
    """Regression: collect_review_issues must use corpus-derived prefix, not hardcoded."""

    def test_design_review_prefix_collected(self, tmp_path: Path):
        """design-review-e*.md files must be scanned when corpus uses design-review prefix."""
        _TECH_DESIGN_EVAL = _EVAL_SCRIPTS.parents[1] / "lulu-design" / "scripts" / "eval"
        if str(_TECH_DESIGN_EVAL) not in sys.path:
            sys.path.insert(0, str(_TECH_DESIGN_EVAL))
        from tech_design_eval_adapter import TechDesignEvalAdapter  # noqa: WPS433
        from workflow_paths import seed_profile_pointer_for_tests  # noqa: WPS433

        cycle = "feat-design-collect"
        cache = Path(".cache/cursor/lulu-dev-workflow")
        base = tmp_path / cache / cycle / "lulu-design"
        base.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        seed_profile_pointer_for_tests(tmp_path, cycle, "lulu-design")
        ws = base / "revision1" / "workflow-state.md"
        ws.parent.mkdir(parents=True, exist_ok=True)
        (ws.parent / "design-doc.md").write_text("# design\n", encoding="utf-8")
        from workflow_state_schema import init_drafting  # noqa: WPS433

        init_drafting(ws, mode="tech")

        adapter = TechDesignEvalAdapter()
        token = eval_control._ADAPTER_CTX.set(adapter)
        try:
            eval_dir = ws.parent / "evaluate1"
            eval_dir.mkdir(parents=True, exist_ok=True)
            review_header = (
                "# Design Review — D1 | revision1 round 1\n\n"
                "**Date:** 2026-01-01\n**Refs:** codebase\n\n"
                "| ID | root_cause | sot_ref | location | severity | evidence | description | status | decision |\n"
                "|----|------------|---------|----------|----------|----------|-------------|--------|----------|\n"
            )
            review_content = (
                review_header
                + "| d1-1 | WO-ERROR | — | design-doc §1 | minor | ev | desc | pending | — |\n"
            )
            (eval_dir / "design-review-e11.md").write_text(review_content, encoding="utf-8")
            (eval_dir / "tech-review-e11.md").write_text(review_content, encoding="utf-8")

            issues, paths = collect_review_issues(eval_dir, cycle_id=cycle, project_root=tmp_path)
        finally:
            eval_control._ADAPTER_CTX.reset(token)

        collected_names = [Path(p).name for p in paths]
        assert "design-review-e11.md" in collected_names, "design-review file must be collected"
        assert "tech-review-e11.md" not in collected_names, "wrong-prefix file must be ignored"
        assert len(issues) == 1
        assert issues[0]["dimension"] == "d1"
