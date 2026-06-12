#!/usr/bin/env python3
"""Tests for eval_control.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_control import (  # noqa: E402
    begin_dimension,
    begin_eval_round,
    build_eval_loop_payload,
    check_dimension,
    complete_round,
    dispatch_list,
    init_round,
    resolve_execution_mode,
)
from evaluate_state_schema import (  # noqa: E402
    init_evaluate_state,
    load_evaluate_state,
    save_evaluate_state,
)
from workflow_state_schema import init_drafting, save_workflow_state  # noqa: E402

_CYCLE = "feat-eval-control"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_SCRIPT = Path(__file__).resolve().parent / "eval_control.py"


def _seed_session(tmp_path: Path, *, active_doc: int = 1) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws = base / f"revision{active_doc}" / "workflow-state.md"
    return ws


class TestDispatchList:
    def test_product_mode(self):
        assert dispatch_list("product") == ["e1", "e2", "e3"]

    def test_tech_mode(self):
        assert dispatch_list("tech") == ["e2", "e3"]

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="invalid mode"):
            dispatch_list("invalid")


class TestInitRound:
    def test_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")

        result = init_round(_CYCLE, tmp_path, mode="product")

        assert result["ok"] is True
        assert result["command"] == "init-round"
        assert result["mode"] == "product"
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["phase"] == "evaluate"
        assert es["current_dimension"] == "e1"
        assert es["e1_status"] == "pending"
        assert es["e2_status"] == "pending"
        assert es["e3_status"] == "pending"

    def test_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = init_round(_CYCLE, tmp_path, mode="tech")

        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "e2"
        assert es["e1_status"] == "complete"
        assert es["e2_status"] == "pending"
        assert es["e3_status"] == "pending"

    def test_invalid_mode_raises(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        with pytest.raises(ValueError, match="invalid mode"):
            init_round(_CYCLE, tmp_path, mode="invalid")


def _setup_evaluating(tmp_path: Path, *, mode: str = "product") -> Path:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode=mode, product_ref="/p.md" if mode == "product" else None)
    save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})
    init_evaluate_state(ws.parent / "evaluate-state.md", mode=mode)
    return ws


class TestBuildEvalLoopPayload:
    def test_success(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        payload = build_eval_loop_payload(_CYCLE, tmp_path)
        assert payload["ok"] is True
        assert payload["command"] == "begin-eval-round"
        assert payload["dispatch"] == ["e1", "e2", "e3"]


class TestBeginEvalRound:
    def test_from_drafting_enters_evaluating_and_returns_payload(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")

        result = begin_eval_round(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["command"] == "begin-eval-round"
        assert result["current_state"] == "Evaluating"
        assert result["evaluate_round"] == 1
        assert result["dispatch"] == ["e1", "e2", "e3"]
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["phase"] == "evaluate"
        assert es["current_dimension"] == "e1"

    def test_idempotent_when_already_evaluating(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["dispatch"] == ["e1", "e2", "e3"]

    def test_tech_mode_dispatch(self, tmp_path: Path):
        _setup_evaluating(tmp_path, mode="tech")
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["dispatch"] == ["e2", "e3"]

    def test_rejects_mismatched_evaluate_state(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path, mode="product")
        es_path = ws.parent / "evaluate-state.md"
        es = load_evaluate_state(es_path)
        es["e1_status"] = "complete"
        from evaluate_state_schema import save_evaluate_state  # noqa: WPS433

        save_evaluate_state(es_path, es)
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "e1_status" in result["reason"]

    def test_rejects_non_drafting_non_evaluating_state(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        save_workflow_state(ws, {"current_state": "ReadyForDelivery"})
        result = begin_eval_round(_CYCLE, tmp_path)
        assert result["ok"] is False


class TestBeginEvalRoundCli:
    def test_json_stdout_on_success(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "begin-eval-round",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True
        assert payload["command"] == "begin-eval-round"


class TestResolveExecutionMode:
    def test_defaults_to_guided_without_cycles_json(self, tmp_path: Path):
        assert resolve_execution_mode(_CYCLE, tmp_path) == "guided"

    def test_reads_autonomous_from_cycles_json(self, tmp_path: Path):
        cache_dir = tmp_path / _CACHE
        cache_dir.mkdir(parents=True)
        (cache_dir / "cycles.json").write_text(
            json.dumps({_CYCLE: {"name": "x", "execution_mode": "autonomous"}}),
            encoding="utf-8",
        )
        assert resolve_execution_mode(_CYCLE, tmp_path) == "autonomous"


class TestBeginDimension:
    def test_marks_in_progress_and_returns_runner_input(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is True
        assert result["command"] == "begin-dimension"
        assert result["dim"] == "e2"
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "e2"
        assert es["e2_status"] == "in_progress"

        runner_input = result["runner_input"]
        assert runner_input["DIMENSION"] == "e2"
        assert runner_input["EXECUTION_MODE"] == "guided"
        assert runner_input["TECH_DOC_PATH"].endswith("revision1/tech-doc.md")
        assert "PRODUCT_REF" not in runner_input

        dispatch_input = result["dispatch_input"]
        assert "DIMENSION:            e2" in dispatch_input
        assert "EXECUTION_MODE:       guided" in dispatch_input

    def test_e1_includes_product_ref(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        result = begin_dimension(_CYCLE, tmp_path, dim="e1")
        assert result["ok"] is True
        assert result["runner_input"]["PRODUCT_REF"] == "/p.md"
        assert "PRODUCT_REF:          /p.md" in result["dispatch_input"]

    def test_rejects_dim_not_in_dispatch_for_tech_mode(self, tmp_path: Path):
        _setup_evaluating(tmp_path, mode="tech")
        result = begin_dimension(_CYCLE, tmp_path, dim="e1")
        assert result["ok"] is False
        assert "not in dispatch list" in result["reason"]

    def test_rejects_non_evaluating_state(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_workflow_state(ws, {"current_state": "Drafting", "evaluate_round": "1"})
        result = begin_dimension(_CYCLE, tmp_path, dim="e2")
        assert result["ok"] is False


_REVIEW_E2 = (
    "# Tech Review — E2 | Round 1\n\n"
    "| ID | Location | Severity | Description | Status | Decision |\n"
    "|----|----------|----------|-------------|--------|----------|\n"
    "| e2-1 | §3 | critical | missing error handling | ✅ Fixed | fix |\n"
    "| e2-2 | §5 | minor | naming inconsistency | Ignored | ignore |\n"
)


def _setup_complete_round_ready(
    tmp_path: Path,
    *,
    mode: str = "product",
) -> Path:
    ws = _seed_session(tmp_path)
    init_drafting(ws, mode=mode, product_ref="/p.md" if mode == "product" else None)
    save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})
    init_evaluate_state(ws.parent / "evaluate-state.md", mode=mode)
    es_path = ws.parent / "evaluate-state.md"
    es = load_evaluate_state(es_path)
    dims = dispatch_list(mode)
    for dim in dims:
        es[f"{dim}_status"] = "complete"
    es["current_dimension"] = dims[-1]
    es["e2_total_issues"] = "2"
    es["e2_resolved_issues"] = "1"
    es["total_issues"] = "2"
    es["resolved_issues"] = "1"
    save_evaluate_state(es_path, es, merge=False)

    eval_dir = ws.parent / "evaluate1"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "tech-review-e12.md").write_text(_REVIEW_E2, encoding="utf-8")
    return ws


class TestCheckDimension:
    def test_complete_outcome_exit_zero(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"current_dimension": "e2"},
        )
        result = check_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is True
        assert result["command"] == "check-dimension"
        assert result["outcome"] == "complete"
        assert result["abandoned"] is False
        assert result["dim_status"] == "complete"
        assert len(result["issues"]) == 2
        assert result["review_path"].endswith("tech-review-e12.md")

    def test_abandoned_outcome_exit_zero(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {
                "current_dimension": "abandoned",
                "e2_status": "in_progress",
            },
        )
        result = check_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is True
        assert result["outcome"] == "abandoned"
        assert result["abandoned"] is True

    def test_incomplete_outcome_exit_nonzero_via_emit(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {
                "current_dimension": "e2",
                "e2_status": "in_progress",
            },
        )
        result = check_dimension(_CYCLE, tmp_path, dim="e2")

        assert result["ok"] is False
        assert result["outcome"] == "incomplete"
        assert result["abandoned"] is False

    def test_rejects_dim_not_in_dispatch_for_tech_mode(self, tmp_path: Path):
        _setup_evaluating(tmp_path, mode="tech")
        result = check_dimension(_CYCLE, tmp_path, dim="e1")
        assert result["ok"] is False


class TestCheckDimensionCli:
    def test_abandoned_exit_zero(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"current_dimension": "abandoned", "e2_status": "in_progress"},
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "check-dimension",
                "--dim",
                "e2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["abandoned"] is True

    def test_incomplete_exit_nonzero(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"current_dimension": "e2", "e2_status": "in_progress"},
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "check-dimension",
                "--dim",
                "e2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["outcome"] == "incomplete"


class TestCompleteRound:
    def test_writes_done_and_returns_summary(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        result = complete_round(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["command"] == "complete-round"
        assert result["current_dimension"] == "done"
        assert result["fix_severity"] == "critical"
        assert result["fix_severity_reason"] == "e2-1: missing error handling"
        assert result["counts"]["ignored_issues"] == 1
        assert len(result["issues"]) == 2

        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "done"
        assert es["fix_severity"] == "critical"

    def test_all_ignored_uses_minor_severity(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        eval_dir = ws.parent / "evaluate1"
        (eval_dir / "tech-review-e12.md").write_text(
            "# Review\n\n"
            "| ID | Location | Severity | Description | Status | Decision |\n"
            "|----|----------|----------|-------------|--------|----------|\n"
            "| e2-1 | §3 | critical | missing error handling | Ignored | ignore |\n",
            encoding="utf-8",
        )
        result = complete_round(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["fix_severity"] == "minor"

    def test_rejects_incomplete_dimension(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        es_path = ws.parent / "evaluate-state.md"
        es = load_evaluate_state(es_path)
        es["e3_status"] = "pending"
        save_evaluate_state(es_path, es)
        result = complete_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "e3_status" in result["reason"]

    def test_rejects_already_done(self, tmp_path: Path):
        ws = _setup_complete_round_ready(tmp_path)
        save_evaluate_state(
            ws.parent / "evaluate-state.md",
            {"current_dimension": "done"},
        )
        result = complete_round(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert "already complete" in result["reason"]


class TestCompleteRoundCli:
    def test_json_stdout_on_success(self, tmp_path: Path):
        _setup_complete_round_ready(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "complete-round",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True
        assert payload["command"] == "complete-round"


class TestBeginDimensionCli:
    def test_plaintext_stdout_on_success(self, tmp_path: Path):
        _setup_evaluating(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "begin-dimension",
                "--dim",
                "e2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout.startswith("DIMENSION:")
        assert "EXECUTION_MODE:" in proc.stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(proc.stdout)

    def test_json_stdout_on_failure(self, tmp_path: Path):
        ws = _setup_evaluating(tmp_path)
        save_workflow_state(ws, {"current_state": "Drafting", "evaluate_round": "1"})
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                "begin-dimension",
                "--dim",
                "e2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False
