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
    dispatch_list,
    init_round,
    resolve_execution_mode,
)
from evaluate_state_schema import init_evaluate_state, load_evaluate_state  # noqa: E402
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
