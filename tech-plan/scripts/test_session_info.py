#!/usr/bin/env python3
"""Tests for tech-plan session_info.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hook_guard import load_transitions  # noqa: E402
from session_info import (  # noqa: E402
    delivery_preview,
    eval_dispatch,
    eval_summary,
    get_session_info,
    session_snapshot,
    stage_transitions,
)
from workflow_common import STAGE  # noqa: E402
from workflow_state_schema import save_workflow_state  # noqa: E402

_SCRIPT = Path(__file__).resolve().parent / "session_info.py"


def _expected_next_stages(cycle_id: str) -> list[str]:
    cycle_type = "topic" if cycle_id.startswith("topic-") else "feature"
    return sorted(load_transitions(cycle_type).get(STAGE, set()))


def _setup_cycle(tmp_path: Path) -> tuple[Path, str]:
    cycle_id = "feat-session-info"
    base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "tech" / "plan"
    revision = base / "revision1"
    revision.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\n---\n",
        encoding="utf-8",
    )
    (revision / "tech-doc.md").write_text(
        "---\n\n"
        "# Feature X\n\n"
        "## North Star\n\n"
        "Deliver a unified session info facade.\n\n"
        "## Key Decisions\n\n"
        "KD.\n",
        encoding="utf-8",
    )
    from workflow_state_schema import init_drafting  # noqa: WPS433

    ws_path = revision / "workflow-state.md"
    init_drafting(ws_path, mode="product", product_ref="/p.md")
    save_workflow_state(ws_path, {"current_state": "ReadyForDelivery"})
    return tmp_path, cycle_id


def _setup_evaluating_cycle(tmp_path: Path) -> tuple[Path, str]:
    project_root, cycle_id = _setup_cycle(tmp_path)
    from evaluate_state_schema import save_evaluate_state  # noqa: WPS433
    from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    save_workflow_state(ws_path, {
        "current_state": "Evaluating",
        "evaluate_round": "1",
    })
    revision = ws_path.parent
    save_evaluate_state(
        revision / "evaluate-state.md",
        {
            "version": "1",
            "phase": "evaluate",
            "current_dimension": "done",
            "e1_status": "pending",
            "e1_total_issues": "0",
            "e1_resolved_issues": "0",
            "e2_status": "complete",
            "e2_total_issues": "2",
            "e2_resolved_issues": "1",
            "e3_status": "pending",
            "e3_total_issues": "0",
            "e3_resolved_issues": "0",
            "total_issues": "2",
            "resolved_issues": "1",
            "fix_severity": "critical",
            "fix_severity_reason": "e2-1 missing error handling",
        },
        merge=False,
    )
    eval_dir = revision / "evaluate1"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "tech-review-e12.md").write_text(
        "# Tech Review — E2 | Round 1\n\n"
        "| ID | Location | Severity | Description | Status | Decision |\n"
        "|----|----------|----------|-------------|--------|----------|\n"
        "| e2-1 | §3 | critical | missing error handling | ✅ Fixed | fix |\n"
        "| e2-2 | §5 | minor | naming inconsistency | Ignored | ignore |\n",
        encoding="utf-8",
    )
    return project_root, cycle_id


class TestEvalDispatch:
    def test_product_mode_dispatch(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        payload = eval_dispatch(cycle_id, project_root)
        assert payload["ok"] is True
        assert payload["view"] == "eval-dispatch"
        assert payload["mode"] == "product"
        assert payload["dispatch"] == ["e1", "e2", "e3"]
        assert payload["evaluate_round"] == 1
        assert payload["M"] == 1
        assert payload["M"] == payload["evaluate_round"]
        assert payload["active_doc"] == 1
        assert payload["N"] == 1
        assert payload["N"] == payload["active_doc"]
        assert payload["current_state"] == "Evaluating"

    def test_tech_mode_dispatch(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        save_workflow_state(ws_path, {"mode": "tech"})
        payload = eval_dispatch(cycle_id, project_root)
        assert payload["ok"] is True
        assert payload["dispatch"] == ["e2", "e3"]

    def test_rejects_non_evaluating_state(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        save_workflow_state(ws_path, {"current_state": "Drafting", "evaluate_round": "1"})
        payload = eval_dispatch(cycle_id, project_root)
        assert payload["ok"] is False
        assert payload["command"] == "eval-dispatch"

    def test_rejects_missing_evaluate_state(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        (ws_path.parent / "evaluate-state.md").unlink()
        payload = eval_dispatch(cycle_id, project_root)
        assert payload["ok"] is False
        assert "evaluate-state.md not found" in payload["message"]

    def test_cli_success(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "eval-dispatch",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["dispatch"] == ["e1", "e2", "e3"]

    def test_cli_failure(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        save_workflow_state(ws_path, {"current_state": "Drafting", "evaluate_round": "1"})
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "eval-dispatch",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["command"] == "eval-dispatch"


class TestEvalSummary:
    def test_returns_eval_fields(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        payload = eval_summary(cycle_id, project_root)
        assert payload["ok"] is True
        assert payload["view"] == "eval-summary"
        assert payload["evaluate_round"] == 1
        assert payload["fix_severity"] == "critical"
        assert payload["counts"]["total_issues"] == 2
        assert payload["counts"]["resolved_issues"] == 1
        assert payload["counts"]["ignored_issues"] == 1
        assert len(payload["issues"]) == 2
        assert payload["issues"][0]["id"] == "e2-1"
        assert payload["issues"][0]["dimension"] == "e2"

    def test_rejects_non_evaluating_state(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        save_workflow_state(ws_path, {"current_state": "Drafting", "evaluate_round": "1"})
        payload = eval_summary(cycle_id, project_root)
        assert payload["ok"] is False
        assert payload["command"] == "eval-summary"

    def test_rejects_incomplete_dimension(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        from evaluate_state_schema import save_evaluate_state  # noqa: WPS433
        from workflow_state_schema import resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        save_evaluate_state(
            ws_path.parent / "evaluate-state.md",
            {"current_dimension": "e2"},
        )
        payload = eval_summary(cycle_id, project_root)
        assert payload["ok"] is False
        assert "done" in payload["message"]


class TestDeliveryPreview:
    def test_returns_delivery_fields(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = delivery_preview(cycle_id, project_root)
        assert payload["ok"] is True
        assert payload["view"] == "delivery-preview"
        assert payload["active_doc"] == 1
        assert payload["current_state"] == "ReadyForDelivery"
        assert payload["tech_doc"]["title"] == "Feature X"
        assert "session info facade" in payload["tech_doc"]["summary"]
        assert payload["tech_doc"]["path"].endswith("revision1/tech-doc.md")

    def test_rejects_non_ready_for_delivery_state(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        from workflow_state_schema import init_drafting, resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        init_drafting(ws_path, mode="tech")
        payload = delivery_preview(cycle_id, project_root)
        assert payload["ok"] is False
        assert payload["command"] == "delivery-preview"
        assert payload["current_state"] == "Drafting"
        assert "ReadyForDelivery" in payload["message"]


class TestSessionSnapshot:
    def test_returns_workflow_and_tech_doc(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = session_snapshot(cycle_id, project_root)
        assert payload["view"] == "session"
        assert payload["workflow_state"]["mode"] == "product"
        assert payload["tech_doc"]["revision"] == 1


class TestStageTransitions:
    def test_matches_transition_table_for_feature(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        payload = stage_transitions(cycle_id, project_root)
        assert payload == {"next_stages": _expected_next_stages(cycle_id)}

    def test_matches_transition_table_for_topic(self, tmp_path: Path):
        project_root, _ = _setup_cycle(tmp_path)
        cycle_id = "topic-session-info"
        payload = stage_transitions(cycle_id, project_root)
        assert payload == {"next_stages": _expected_next_stages(cycle_id)}


class TestGetSessionInfo:
    def test_unknown_view_raises(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        with pytest.raises(ValueError, match="unknown view"):
            get_session_info(cycle_id, project_root, view="invalid")


class TestCli:
    def test_delivery_preview_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "delivery-preview",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["view"] == "delivery-preview"
        assert payload["tech_doc"]["title"] == "Feature X"

    def test_delivery_preview_cli_failure(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        from workflow_state_schema import init_drafting, resolve_workflow_state_path_from_cycle  # noqa: WPS433

        ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
        init_drafting(ws_path, mode="tech")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "delivery-preview",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["command"] == "delivery-preview"

    def test_eval_summary_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_evaluating_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "eval-summary",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["view"] == "eval-summary"
        assert payload["fix_severity"] == "critical"

    def test_stage_transitions_view(self, tmp_path: Path):
        project_root, cycle_id = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-id",
                cycle_id,
                "--project-root",
                str(project_root),
                "--view",
                "stage-transitions",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload == {"next_stages": _expected_next_stages(cycle_id)}
