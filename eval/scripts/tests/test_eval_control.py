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
from review_io import parse_review_file  # noqa: E402
from eval_control import (  # noqa: E402
    artifact_remediation_complete,
    begin_artifact_remediation,
    begin_dimension,
    begin_dimension_artifact_remediation,
    begin_eval_round,
    begin_dimension_human_resolution,
    begin_human_resolution,
    build_eval_loop_payload,
    check_dimension,
    check_dimension_artifact_remediation,
    check_dimension_human_resolution,
    collect_review_issues,
    complete_round,
    compute_fix_severity,
    dispatch_list,
    init_round,
    probe_complete,
    read_b_snapshot_cmd,
    human_resolution_complete,
    submit_remediation_diff,
    submit_probe_findings,
)
from evaluate_state_ops import (  # noqa: E402
    dimension_status_legacy_map,
    init_evaluate_state_for_corpus,
    merge_current_dimension,
)
from evaluate_state_schema import (  # noqa: E402
    load_evaluate_state,
    parse_dimension_tokens,
    parse_issue_counts,
    patch_issue_count,
    save_evaluate_state,
)
from init_working_helpers import (  # noqa: E402
    init_working_ready,
    mark_focus_evaluating,
    mark_focus_intake_done,
    product_delivered_refs,
    seed_frozen_delivered,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    save_workflow_state,
)

_CYCLE = "feat-eval-control"
from tech_plan_eval_adapter import LULU_PLAN_COMPOSED_CORPUS_REF, TechPlanEvalAdapter  # noqa: E402

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
def _set_eval_context():
    adapter_token = eval_control._ADAPTER_CTX.set(_ADAPTER)
    workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-plan")
    handoff_token = eval_control._HANDOFF_CTX.set(None)
    yield
    eval_control._ADAPTER_CTX.reset(adapter_token)
    eval_control._WORKFLOW_ID_CTX.reset(workflow_token)
    eval_control._HANDOFF_CTX.reset(handoff_token)

_REVIEW_HEADER = (
    "# Tech Review — E2 | revision1 round 1\n\n"
    "**Date:** 2026-01-01\n"
    "**Refs:** codebase\n\n"
    "| ID | root_cause | sot_ref | location | severity | evidence "
    "| description | status | decision | resolution |\n"
    "|----|------------|---------|----------|----------|----------"
    "|-------------|--------|----------|------------|\n"
)

_REVIEW_E2_PROBE = (
    _REVIEW_HEADER
    + "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | missing handling | "
    "missing error handling | pending | — | |\n"
    + "| e2-2 | WO-ERROR | — | tech-doc §5 | minor | naming | "
    "naming inconsistency | pending | — | |\n"
)

_REVIEW_E2_DONE = (
    _REVIEW_HEADER
    + "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | missing handling | "
    "missing error handling | fixed | fix | |\n"
    + "| e2-2 | WO-ERROR | — | tech-doc §5 | minor | naming | "
    "naming inconsistency | ignored | ignore | |\n"
)

_E2_FINDINGS = [
    {
        "id": "e2-1",
        "root_cause": "WO-ERROR",
        "location": "tech-doc §3",
        "severity": "critical",
        "evidence": "missing handling",
        "description": "missing error handling",
    },
    {
        "id": "e2-2",
        "root_cause": "WO-ERROR",
        "location": "tech-doc §5",
        "severity": "minor",
        "evidence": "naming",
        "description": "naming inconsistency",
    },
]


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
    init_working_ready(ws, mode=mode)
    if mode == "product":
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
    mark_focus_intake_done(ws.parent)
    mark_focus_evaluating(ws.parent)
    save_workflow_state(ws, {"current_state": "Working", "evaluate_round": "1"})
    target_doc = ws.parent / "L1" / "tech-doc.md"
    target_doc.parent.mkdir(parents=True, exist_ok=True)
    target_doc.write_text("# Tech Doc\n", encoding="utf-8")
    _init_evaluate_state(ws.parent / "evaluate-state.md", cycle_id=_CYCLE, tmp_path=tmp_path)
    return ws


def _write_review(ws: Path, content: str, *, filename: str = "tech-review-e11.md") -> Path:
    eval_dir = ws.parent / "evaluate1"
    eval_dir.mkdir(parents=True, exist_ok=True)
    path = eval_dir / filename
    normalized_lines: list[str] = []
    for line in content.splitlines():
        if (
            line.startswith("|")
            and not line.startswith("|---")
            and "severity" not in line.lower()
            and line.count("|") == 10
        ):
            line += " |"
        normalized_lines.append(line)
    path.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")
    return path


def _submit_probe(
    tmp_path: Path,
    *,
    dimension_token: str,
    findings: list[dict[str, str]],
) -> dict:
    payload_path = tmp_path / f"{dimension_token}-findings.json"
    payload_path.write_text(
        json.dumps({
            "dimension_token": dimension_token,
            "findings": findings,
        }),
        encoding="utf-8",
    )
    return submit_probe_findings(
        _CYCLE,
        tmp_path,
        payload_file=payload_path,
    )


def _submit_remediation(
    tmp_path: Path,
    *,
    dimension_token: str,
    base_digest: str,
    unified_diff: str,
    issue_ids: list[str],
) -> dict:
    payload_path = tmp_path / f"{dimension_token}-remediation.json"
    payload_path.write_text(
        json.dumps({
            "dimension_token": dimension_token,
            "base_digest": base_digest,
            "unified_diff": unified_diff,
            "issue_ids": issue_ids,
        }),
        encoding="utf-8",
    )
    return submit_remediation_diff(
        _CYCLE,
        tmp_path,
        payload_file=payload_path,
    )


def _setup_probed_e2(tmp_path: Path, *, mode: str = "product") -> Path:
    ws = _setup_evaluating(tmp_path, mode=mode)
    context = begin_dimension(_CYCLE, tmp_path, dim="e2")
    _submit_probe(
        tmp_path,
        dimension_token=context["operation_ctx"]["dimension_token"],
        findings=_E2_FINDINGS,
    )
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
        init_working_ready(ws, mode="product")
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3"]

    def test_tech_mode_with_diagnostic_upstream(self, tmp_path: Path):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        ws = _seed_session(tmp_path)
        decision = tmp_path / "decision-doc.md"
        decision.write_text("# Decision\n", encoding="utf-8")
        refs = [DeliveredRef(type="lulu-approach", path=str(decision.resolve()))]
        init_working_ready(ws, mode="tech")
        seed_frozen_delivered(ws, refs)
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3", "e4"]

    def test_tech_mode_without_upstream(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        assert dispatch_list(_CYCLE, tmp_path) == ["e2", "e3"]


class TestInitRound:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
        mark_focus_intake_done(ws.parent)
        result = init_round(_CYCLE, tmp_path, mode="product")
        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "L1" / "evaluate-state.md")
        assert es["version"] == "5"
        assert es["eval_status"] == "active"
        assert es["fix_phase"] == "probe"
        assert es["corpus_ref"] == LULU_PLAN_COMPOSED_CORPUS_REF
        assert es.get("corpus_fingerprint")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map == {"e2": "pending", "e3": "pending"}

    def test_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="tech")
        mark_focus_intake_done(ws.parent)
        init_round(_CYCLE, tmp_path, mode="tech")
        es = load_evaluate_state(ws.parent / "L1" / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map == {"e2": "pending", "e3": "pending"}

    def test_product_mode_without_delivered_refs_uses_base_dims(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        mark_focus_intake_done(ws.parent)
        init_round(_CYCLE, tmp_path, mode="product")
        es = load_evaluate_state(ws.parent / "L1" / "evaluate-state.md")
        assert _dim_map(es, tmp_path) == {"e2": "pending", "e3": "pending"}


class TestBeginEvalRound:
    def test_from_working_enters_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_working_ready(ws, mode="product")
        seed_frozen_delivered(ws, product_delivered_refs("/p.md"))
        mark_focus_intake_done(ws.parent)
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
        assert "expected '5'" in result["reason"]

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


class TestIssueProbeSots:
    def test_resolved_sot_ref_is_the_sot_link(self, tmp_path: Path):
        from eval_operation_context import issue_probe_context  # noqa: WPS433
        from eval_operation_record_schema import get_operation_record  # noqa: WPS433

        source_path = tmp_path / "upstream-intent.md"
        source_path.write_text("# Upstream intent\n", encoding="utf-8")
        target_path = tmp_path / "target.md"
        target_path.write_text("# B\n", encoding="utf-8")
        operations_path = tmp_path / "eval-operations.json"

        ctx = issue_probe_context(
            operations_path=operations_path,
            write_staging_dir=tmp_path / "staging",
            target_path=target_path,
            round_token="round-1",
            dimension_id="tech-conformance",
            method={"ref": "method.md", "focus": "focus"},
            sots=[{"ref": str(source_path.resolve())}],
        )

        sot = ctx["resolved_sots"][0]
        assert sot == {"ref": str(source_path.resolve())}
        record = get_operation_record(operations_path, ctx["dimension_token"])
        assert record["evidence_snapshots"] == {}
        assert record["resolved_sots"][0]["ref"] == str(source_path.resolve())


class TestBeginDimension:
    def test_marks_in_progress_and_returns_token_scoped_context(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert _dim_map(es, tmp_path)["e2"] == "in_progress"
        operation_ctx = result["operation_ctx"]
        assert operation_ctx["dimension_id"] == "codebase-consistency"
        assert operation_ctx["dimension_token"]
        assert operation_ctx["round_token"] == es["round_token"]
        assert operation_ctx["allowed_submission"] == "finding"
        assert operation_ctx["resolved_method"]["ref"].endswith(
            "eval/methods/codebase-consistency.md",
        )
        assert operation_ctx["resolved_sots"][0] == {"ref": "."}
        assert parse_dimension_tokens(es["dimension_tokens"]) == {
            "codebase-consistency": operation_ctx["dimension_token"],
        }
        assert "EVAL_TARGET_PATH" not in result["dispatch_input"]
        snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=operation_ctx["dimension_token"],
        )
        assert snapshot["ok"] is True
        assert snapshot["target_digest"] == operation_ctx["target_digest"]
        assert snapshot["content"]

    def test_commits_staged_state_through_adapter(self, tmp_path: Path, monkeypatch):
        ws = _setup_evaluating(tmp_path)
        original_commit = _ADAPTER.commit_evaluate_state
        captured: dict[str, object] = {}

        def _commit_spy(
            cycle_id: str,
            project_root: Path,
            *,
            staged_state_path: Path,
            set_phase_evaluating: bool = False,
            previous_done_required: bool = False,
        ) -> dict[str, object]:
            captured["path"] = staged_state_path
            captured["state"] = load_evaluate_state(staged_state_path)
            captured["set_phase_evaluating"] = set_phase_evaluating
            captured["previous_done_required"] = previous_done_required
            return original_commit(
                cycle_id,
                project_root,
                staged_state_path=staged_state_path,
                set_phase_evaluating=set_phase_evaluating,
                previous_done_required=previous_done_required,
            )

        monkeypatch.setattr(_ADAPTER, "commit_evaluate_state", _commit_spy)

        result = begin_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is True
        assert Path(str(captured["path"])).name == "evaluate-state.md"
        assert _dim_map(captured["state"], tmp_path)["e2"] == "in_progress"
        assert captured["set_phase_evaluating"] is False
        assert captured["previous_done_required"] is False
        assert _dim_map(load_evaluate_state(ws.parent / "evaluate-state.md"), tmp_path)["e2"] == "in_progress"

    def test_adapter_rejection_leaves_formal_state_unchanged(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        ws = _setup_evaluating(tmp_path)
        es_path = ws.parent / "evaluate-state.md"
        before = es_path.read_bytes()
        captured: dict[str, object] = {}

        def _reject_commit(
            _cycle_id: str,
            _project_root: Path,
            *,
            staged_state_path: Path,
            set_phase_evaluating: bool = False,
            previous_done_required: bool = False,
        ) -> dict[str, object]:
            captured["state"] = load_evaluate_state(staged_state_path)
            return {"ok": False, "error": "test adapter rejection"}

        monkeypatch.setattr(_ADAPTER, "commit_evaluate_state", _reject_commit)

        result = begin_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is False
        assert result["reason"] == "test adapter rejection"
        assert _dim_map(captured["state"], tmp_path)["e2"] == "in_progress"
        assert es_path.read_bytes() == before

    def test_adapter_rejection_discards_provisional_token_context(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        ws = _setup_evaluating(tmp_path)
        operations_path = ws.parent / "evaluate1" / "eval-operations.json"
        staging_root = ws.parent / "evaluate1" / "dimensions"

        monkeypatch.setattr(
            _ADAPTER,
            "commit_evaluate_state",
            lambda *args, **kwargs: {"ok": False, "error": "state rejected"},
        )
        result = begin_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is False
        assert result["reason"] == "state rejected"
        assert not operations_path.exists()
        assert not staging_root.exists()

    def test_accepts_canonical_dim_id(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="codebase-consistency")
        assert result["ok"] is True
        assert result["operation_ctx"]["dimension_id"] == "codebase-consistency"

    def test_parallel_dimensions_receive_isolated_tokens_and_staging(self, tmp_path: Path):
        _setup_evaluating(tmp_path, mode="tech")
        codebase = begin_dimension(_CYCLE, tmp_path, dim="e2")
        quality = begin_dimension(_CYCLE, tmp_path, dim="e3")

        assert codebase["ok"] is True
        assert quality["ok"] is True
        first_ctx = codebase["operation_ctx"]
        second_ctx = quality["operation_ctx"]
        assert first_ctx["round_token"] == second_ctx["round_token"]
        assert first_ctx["dimension_token"] != second_ctx["dimension_token"]
        assert first_ctx["staging_scope"] != second_ctx["staging_scope"]
        assert "EVALUATE_STATE_PATH" not in codebase["dispatch_input"]
        missing = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token="unknown-token",
        )
        assert missing["ok"] is False
        assert "unknown dimension_token" in missing["reason"]

    def test_concurrent_dimensions_keep_isolated_operation_records(self, tmp_path: Path):
        from eval_operation_record_schema import load_operation_records  # noqa: WPS433

        ws = _setup_evaluating(tmp_path, mode="tech")
        start = threading.Barrier(2)
        results: list[dict] = []
        errors: list[str] = []

        def _begin(dim: str) -> None:
            adapter_token = eval_control._ADAPTER_CTX.set(_ADAPTER)
            workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-plan")
            try:
                start.wait()
                result = begin_dimension(_CYCLE, tmp_path, dim=dim)
                if result["ok"]:
                    results.append(result)
                else:
                    errors.append(result["reason"])
            finally:
                eval_control._ADAPTER_CTX.reset(adapter_token)
                eval_control._WORKFLOW_ID_CTX.reset(workflow_token)

        threads = [threading.Thread(target=_begin, args=(dim,)) for dim in ("e2", "e3")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert len(results) == 2
        tokens = {
            result["operation_ctx"]["dimension_token"]
            for result in results
        }
        assert len(tokens) == 2
        operations = load_operation_records(
            ws.parent / "evaluate1" / "eval-operations.json",
        )["operations"]
        assert set(operations) == tokens


class TestSubmitProbeFindings:
    def test_happy_path(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        context = begin_dimension(_CYCLE, tmp_path, dim="e2")
        result = _submit_probe(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            findings=_E2_FINDINGS,
        )
        assert result["ok"] is True
        assert result["outcome"] == "probed"
        assert result["total_issues"] == "2"
        assert result["idempotent"] is False
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert _dim_map(es, tmp_path)["e2"] == "probed"
        counts = parse_issue_counts(es["issue_counts"])
        assert counts["codebase-consistency"]["total"] == "2"

    def test_invalid_payload_leaves_all_runtime_data_unchanged(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        context = begin_dimension(_CYCLE, tmp_path, dim="e2")
        token = context["operation_ctx"]["dimension_token"]
        state_path = ws.parent / "evaluate-state.md"
        operations_path = ws.parent / "evaluate1" / "eval-operations.json"
        state_before = state_path.read_bytes()
        operations_before = operations_path.read_bytes()
        payload_path = tmp_path / "invalid-findings.json"
        payload_path.write_text(
            json.dumps({
                "dimension_token": token,
                "findings": [{"id": "e2-1"}],
            }),
            encoding="utf-8",
        )
        result = submit_probe_findings(
            _CYCLE,
            tmp_path,
            payload_file=payload_path,
        )
        assert result["ok"] is False
        assert state_path.read_bytes() == state_before
        assert operations_path.read_bytes() == operations_before
        assert not (ws.parent / "evaluate1" / "tech-review-e12.md").exists()

    def test_exact_replay_is_idempotent(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        context = begin_dimension(_CYCLE, tmp_path, dim="e2")
        token = context["operation_ctx"]["dimension_token"]
        first = _submit_probe(tmp_path, dimension_token=token, findings=_E2_FINDINGS)
        review_path = Path(first["review_path"])
        review_before = review_path.read_bytes()
        state_before = (ws.parent / "evaluate-state.md").read_bytes()

        replay = _submit_probe(tmp_path, dimension_token=token, findings=_E2_FINDINGS)

        assert first["ok"] is True
        assert replay["ok"] is True
        assert replay["idempotent"] is True
        assert review_path.read_bytes() == review_before
        assert (ws.parent / "evaluate-state.md").read_bytes() == state_before

    def test_conflicting_replay_is_rejected(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        context = begin_dimension(_CYCLE, tmp_path, dim="e2")
        token = context["operation_ctx"]["dimension_token"]
        first = _submit_probe(tmp_path, dimension_token=token, findings=_E2_FINDINGS)
        review_path = Path(first["review_path"])
        review_before = review_path.read_bytes()
        conflicting = [dict(_E2_FINDINGS[0], description="different finding")]

        result = _submit_probe(
            tmp_path,
            dimension_token=token,
            findings=conflicting,
        )

        assert result["ok"] is False
        assert "conflicting submission" in result["reason"]
        assert review_path.read_bytes() == review_before

    def test_concurrent_finish_locked(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path, mode="tech")
        codebase = begin_dimension(_CYCLE, tmp_path, dim="e2")
        quality = begin_dimension(_CYCLE, tmp_path, dim="e3")
        errors: list[str] = []

        def _run(token: str, findings: list[dict[str, str]]) -> None:
            adapter_token = eval_control._ADAPTER_CTX.set(_ADAPTER)
            workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-plan")
            try:
                result = _submit_probe(
                    tmp_path,
                    dimension_token=token,
                    findings=findings,
                )
                if not result["ok"]:
                    errors.append(result["reason"])
            except ValueError as exc:
                errors.append(str(exc))
            finally:
                eval_control._ADAPTER_CTX.reset(adapter_token)
                eval_control._WORKFLOW_ID_CTX.reset(workflow_token)

        t1 = threading.Thread(
            target=_run,
            args=(codebase["operation_ctx"]["dimension_token"], _E2_FINDINGS),
        )
        t2 = threading.Thread(
            target=_run,
            args=(
                quality["operation_ctx"]["dimension_token"],
                [{
                    "id": "e3-1",
                    "root_cause": "WO-ERROR",
                    "location": "loc",
                    "severity": "minor",
                    "evidence": "ev",
                    "description": "d",
                }],
            ),
        )
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
        assert "submit-probe-findings" in result["reason"]

    def test_abandoned_outcome(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = check_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is True
        assert result["abandoned"] is True


class TestProbeComplete:
    def test_advances_fix_phase(self, tmp_path: Path):
        _setup_evaluating(tmp_path, mode="tech")
        for dim in ("e2", "e3"):
            context = begin_dimension(_CYCLE, tmp_path, dim=dim)
            result = _submit_probe(
                tmp_path,
                dimension_token=context["operation_ctx"]["dimension_token"],
                findings=[{
                    "id": f"{dim}-1",
                    "root_cause": "WO-ERROR",
                    "location": "loc",
                    "severity": "minor",
                    "evidence": "ev",
                    "description": "desc",
                }],
            )
            assert result["ok"] is True, result["reason"]
        result = probe_complete(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["fix_phase"] == "human-resolution"
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
        assert result["ok"] is False
        assert "Human Resolution" in result["reason"]

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
        assert "DIMENSION_TOKEN" in result["dispatch_input"]
        assert "BASE_DIGEST" in result["dispatch_input"]
        assert "REMEDIATION_TARGET_PATH" not in result["dispatch_input"]

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
        assert result["fix_phase"] == "done"

    def test_early_dim_complete_when_no_pending_human(self, tmp_path: Path):
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
        artifact_remediation_complete(_CYCLE, tmp_path)
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        dim_map = _dim_map(es, tmp_path)
        assert dim_map["e2"] == "complete"
        assert dim_map["e3"] == "complete"


class TestSubmitRemediationDiff:
    @staticmethod
    def _context(tmp_path: Path) -> tuple[Path, dict, dict]:
        ws = _setup_evaluating(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        target.write_text(
            "# Tech Doc\nrepeat\ntarget\nrepeat\n",
            encoding="utf-8",
        )
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "artifact-remediation"},
        )
        _write_review(ws, _REVIEW_E2_PROBE)
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            _merge_dim(es, "e2", "probed", tmp_path),
            merge=False,
        )
        context = begin_dimension_artifact_remediation(_CYCLE, tmp_path, dim="e2")
        snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
        )
        return ws, context, snapshot

    @staticmethod
    def _diff(replacement: str = "patched") -> str:
        return (
            "@@ -2,3 +2,3 @@\n"
            " repeat\n"
            "-target\n"
            f"+{replacement}\n"
            " repeat\n"
        )

    @staticmethod
    def _review(ws: Path) -> Path:
        return next((ws.parent / "evaluate1").glob("tech-review-e*.md"))

    def test_applies_repeated_text_only_at_declared_hunk(self, tmp_path: Path):
        ws, context, snapshot = self._context(tmp_path)
        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        target = ws.parent / "L1" / "tech-doc.md"
        assert result["ok"] is True
        assert target.read_text(encoding="utf-8") == "# Tech Doc\nrepeat\npatched\nrepeat\n"
        rows = parse_review_file(self._review(ws))
        assert next(row for row in rows if row["id"] == "e2-1")["status"] == "fixed"

    def test_stale_base_digest_leaves_all_owned_data_unchanged(self, tmp_path: Path):
        ws, context, _snapshot = self._context(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        before = [path.read_bytes() for path in (target, review, state, operations)]
        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest="0" * 64,
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        assert result["ok"] is False
        assert "base_digest" in result["reason"]
        assert [path.read_bytes() for path in (target, review, state, operations)] == before

    def test_invalid_hunk_context_leaves_all_owned_data_unchanged(self, tmp_path: Path):
        ws, context, snapshot = self._context(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        before = [path.read_bytes() for path in (target, review, state, operations)]
        invalid = "@@ -2,3 +2,3 @@\n repeat\n-not-target\n+patched\n repeat\n"
        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest=snapshot["target_digest"],
            unified_diff=invalid,
            issue_ids=["e2-1"],
        )
        assert result["ok"] is False
        assert "context" in result["reason"]
        assert [path.read_bytes() for path in (target, review, state, operations)] == before

    def test_tampered_snapshot_rejects_diff_without_mutation(self, tmp_path: Path):
        from eval_operation_record_schema import get_operation_record  # noqa: WPS433

        ws, context, snapshot = self._context(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        token = context["operation_ctx"]["dimension_token"]
        record = get_operation_record(operations, token)
        Path(record["snapshot_path"]).write_text("tampered\n", encoding="utf-8")
        before = [path.read_bytes() for path in (target, review, state, operations)]

        result = _submit_remediation(
            tmp_path,
            dimension_token=token,
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )

        assert result["ok"] is False
        assert "snapshot digest mismatch" in result["reason"]
        assert [path.read_bytes() for path in (target, review, state, operations)] == before

    def test_adapter_target_failure_rolls_back_without_eval_writes(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        ws, context, snapshot = self._context(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        before = [path.read_bytes() for path in (target, review, state, operations)]
        monkeypatch.setattr(
            _ADAPTER,
            "commit_remediation_target",
            lambda *args, **kwargs: {"ok": False, "error": "target commit rejected"},
        )
        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        assert result["ok"] is False
        assert result["reason"] == "target commit rejected"
        assert [path.read_bytes() for path in (target, review, state, operations)] == before

    def test_state_adapter_failure_restores_target_and_review(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        ws, context, snapshot = self._context(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        before = [path.read_bytes() for path in (target, review, state, operations)]
        monkeypatch.setattr(
            _ADAPTER,
            "commit_evaluate_state",
            lambda *args, **kwargs: {"ok": False, "error": "state commit rejected"},
        )

        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )

        assert result["ok"] is False
        assert result["reason"] == "state commit rejected"
        assert [path.read_bytes() for path in (target, review, state, operations)] == before

    def test_exact_replay_is_idempotent_and_conflicting_replay_is_rejected(
        self,
        tmp_path: Path,
    ):
        ws, context, snapshot = self._context(tmp_path)
        token = context["operation_ctx"]["dimension_token"]
        first = _submit_remediation(
            tmp_path,
            dimension_token=token,
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        target = ws.parent / "L1" / "tech-doc.md"
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        after_first = [path.read_bytes() for path in (target, review, state, operations)]
        replay = _submit_remediation(
            tmp_path,
            dimension_token=token,
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        conflict = _submit_remediation(
            tmp_path,
            dimension_token=token,
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff("different"),
            issue_ids=["e2-1"],
        )
        assert first["ok"] is True
        assert replay == {
            "ok": True,
            "command": "submit-remediation-diff",
            "dimension_token": token,
            "outcome": "remediated",
            "idempotent": True,
        }
        assert conflict["ok"] is False
        assert "conflicting submission" in conflict["reason"]
        assert [path.read_bytes() for path in (target, review, state, operations)] == after_first

    def test_human_sot_defect_rejects_b_mutation(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        target = ws.parent / "L1" / "tech-doc.md"
        target.write_text("# Tech Doc\nrepeat\ntarget\nrepeat\n", encoding="utf-8")
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"fix_phase": "human-resolution"},
        )
        _write_review(
            ws,
            _REVIEW_HEADER
            + "| e2-1 | SOT-DEFECT | product §1 | loc | critical | ev | desc "
            "| pending | — |\n",
        )
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            _merge_dim(es, "e2", "probed", tmp_path),
            merge=False,
        )
        context = begin_dimension_human_resolution(_CYCLE, tmp_path, dim="e2")
        snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
        )
        review = self._review(ws)
        state = ws.parent / "evaluate-state.md"
        operations = ws.parent / "evaluate1" / "eval-operations.json"
        before = [path.read_bytes() for path in (target, review, state, operations)]
        result = _submit_remediation(
            tmp_path,
            dimension_token=context["operation_ctx"]["dimension_token"],
            base_digest=snapshot["target_digest"],
            unified_diff=self._diff(),
            issue_ids=["e2-1"],
        )
        assert result["ok"] is False
        assert "not authorized for remediation" in result["reason"]
        assert [path.read_bytes() for path in (target, review, state, operations)] == before


@pytest.mark.skip(reason="Replaced by focused Human Resolution control tests")
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
        from session_control import resume_after_eval  # noqa: WPS433

        ws = _setup_complete_round_ready(tmp_path)
        complete_round(_CYCLE, tmp_path)
        result = resume_after_eval(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert load_workflow_state(ws)["current_state"] == "Working"

    def test_failure_when_abandoned(self, tmp_path: Path):
        from session_control import resume_after_eval  # noqa: WPS433

        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(ws.parent / "evaluate-state.md", {"eval_status": "abandoned"})
        result = resume_after_eval(_CYCLE, tmp_path)
        assert result["ok"] is False


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
        init_working_ready(ws, mode="tech")

        adapter = TechDesignEvalAdapter()
        adapter_token = eval_control._ADAPTER_CTX.set(adapter)
        workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-design")
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
            eval_control._ADAPTER_CTX.reset(adapter_token)
            eval_control._WORKFLOW_ID_CTX.reset(workflow_token)

        collected_names = [Path(p).name for p in paths]
        assert "design-review-e11.md" in collected_names, "design-review file must be collected"
        assert "tech-review-e11.md" not in collected_names, "wrong-prefix file must be ignored"
        assert len(issues) == 1
        assert issues[0]["dimension"] == "d1"
