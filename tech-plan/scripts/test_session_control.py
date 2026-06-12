#!/usr/bin/env python3
"""Tests for session_control.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_control import (  # noqa: E402
    _CMD_DELIVER,
    _CMD_READY,
    _CMD_START_EVALUATING,
    deliver,
    ready_for_delivery,
    start_evaluating,
)
from evaluate_state_schema import load_evaluate_state  # noqa: E402
from workflow_state_schema import init_drafting, load_workflow_state, save_workflow_state

_CYCLE = "feat-test"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")


def _seed_session(tmp_path: Path, active_doc: int = 1) -> Path:
    base = tmp_path / _CACHE / _CYCLE / "tech" / "plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws = base / f"revision{active_doc}" / "workflow-state.md"
    return ws


class TestStartEvaluating:
    def test_from_drafting_product_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")

        result = start_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "Evaluating"
        assert result["evaluate_round"] == 1
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Evaluating"
        assert loaded["evaluate_round"] == "1"
        assert "skip_evaluate_requested" not in loaded
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "e1"
        assert es["e1_status"] == "pending"

    def test_from_drafting_tech_mode(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = start_evaluating(_CYCLE, tmp_path)

        assert result["ok"] is True
        es = load_evaluate_state(ws.parent / "evaluate-state.md")
        assert es["current_dimension"] == "e2"
        assert es["e1_status"] == "complete"
        assert es["e2_status"] == "pending"

    def test_increments_evaluate_round(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech", evaluate_round=1)
        save_workflow_state(ws, {"current_state": "Drafting", "evaluate_round": "1"})
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["evaluate_round"] == 2
        loaded = load_workflow_state(ws)
        assert loaded["evaluate_round"] == "2"

    def test_idempotent_when_already_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        start_evaluating(_CYCLE, tmp_path)
        es_path = ws.parent / "evaluate-state.md"
        es = load_evaluate_state(es_path)
        es["e2_status"] = "in_progress"
        from evaluate_state_schema import save_evaluate_state  # noqa: WPS433

        save_evaluate_state(es_path, es)
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["evaluate_round"] == 1
        reloaded = load_evaluate_state(es_path)
        assert reloaded["e2_status"] == "in_progress"

    def test_failure_from_ready_for_delivery(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        result = start_evaluating(_CYCLE, tmp_path)
        assert result["ok"] is False
        assert result["current_state"] == "ReadyForDelivery"


class TestReadyForDelivery:
    def test_from_drafting_sets_skip_flag(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is True
        assert result["current_state"] == "ReadyForDelivery"
        loaded = load_workflow_state(ws)
        assert loaded["skip_evaluate_requested"] == "true"

    def test_from_evaluating_omits_skip_flag(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Evaluating", "evaluate_round": "1"})

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is True
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "ReadyForDelivery"
        assert "skip_evaluate_requested" not in loaded

    def test_idempotent_when_already_ready(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        result = ready_for_delivery(_CYCLE, tmp_path)
        assert result["ok"] is True
        assert result["current_state"] == "ReadyForDelivery"

    def test_failure_from_delivered(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        ready_for_delivery(_CYCLE, tmp_path)
        deliver(_CYCLE, tmp_path)

        result = ready_for_delivery(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["resume"]["entry"] == "Delivered"
        assert "ready-for-delivery" in result["resume"]["action"]


class TestDeliver:
    def test_success_from_ready_for_delivery(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="product", product_ref="/p.md")
        ready_for_delivery(_CYCLE, tmp_path)

        result = deliver(_CYCLE, tmp_path, note="confirmed")

        assert result["ok"] is True
        assert result["current_state"] == "Delivered"
        loaded = load_workflow_state(ws)
        assert loaded["current_state"] == "Delivered"
        assert "skip_evaluate_requested" not in loaded
        gate = ws.parent / "human-delivery-gate.md"
        assert gate.exists()
        assert "confirmed" in gate.read_text(encoding="utf-8")

    def test_failure_from_evaluating(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        save_workflow_state(ws, {"current_state": "Evaluating"})

        result = deliver(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert result["current_state"] == "Evaluating"
        assert result["message"] == (
            "deliver 被拒绝：当前状态为 Evaluating，"
            "预期状态为 ReadyForDelivery。请暂停执行，等待用户指示。"
        )
        assert "resume" not in result

    def test_failure_from_drafting(self, tmp_path: Path):
        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")

        result = deliver(_CYCLE, tmp_path)

        assert result["ok"] is False
        assert "Drafting" in result["message"]
        assert "resume" not in result


class TestCli:
    def test_start_evaluating_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        script = Path(__file__).resolve().parent / "session_control.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                _CMD_START_EVALUATING,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True
        assert payload["command"] == _CMD_START_EVALUATING
        assert payload["evaluate_round"] == 1

    def test_deliver_failure_json_on_stdout(self, tmp_path: Path):
        import subprocess

        ws = _seed_session(tmp_path)
        init_drafting(ws, mode="tech")
        script = Path(__file__).resolve().parent / "session_control.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cycle-id",
                _CYCLE,
                "--project-root",
                str(tmp_path),
                _CMD_DELIVER,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False
        assert payload["command"] == _CMD_DELIVER
        assert "message" in payload
        assert "resume" not in payload
        assert "ReadyForDelivery" in payload["message"]
