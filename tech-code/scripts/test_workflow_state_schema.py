#!/usr/bin/env python3
"""Tests for workflow_state_schema.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflow_state_schema import (
    get_schema,
    init_preparing,
    load_workflow_state,
    mark_historical,
    resolve_workflow_state_path,
    save_workflow_state,
    validate_workflow_state,
)

_SCRIPT = Path(__file__).resolve().parent / "workflow_state_schema.py"

_REQUIRED_FIELD_NAMES = {
    "version",
    "workflow",
    "current_state",
    "mode",
    "task_list_ref",
    "current_task",
    "current_phase",
    "updated_at",
}

_VALID_DATA = {
    "version": "1",
    "workflow": "tech-code",
    "current_state": "Executing",
    "mode": "work-order",
    "task_list_ref": "/path/to/code-task-list.md",
    "current_task": "t1",
    "current_phase": "WriteTests",
    "updated_at": "2024-01-01T00:00:00+00:00",
}


def _write_valid(path: Path, **overrides) -> None:
    data = {**_VALID_DATA, **overrides}
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


class TestGetSchema:
    def test_contains_all_required_fields(self):
        field_names = {s["field"] for s in get_schema()}
        assert _REQUIRED_FIELD_NAMES.issubset(field_names)

    def test_required_fields_marked_required(self):
        for entry in get_schema():
            if entry["field"] in _REQUIRED_FIELD_NAMES:
                assert entry["required"] is True

    def test_historical_is_optional(self):
        historical = next(s for s in get_schema() if s["field"] == "historical")
        assert historical["required"] is False

    def test_current_state_description_mentions_enum(self):
        state_field = next(s for s in get_schema() if s["field"] == "current_state")
        assert "Preparing" in state_field["description"]
        assert "Delivered" in state_field["description"]

    def test_returns_copy(self):
        s1 = get_schema()
        s2 = get_schema()
        s1.clear()
        assert len(s2) > 0


class TestValidateWorkflowState:
    def test_valid_data_returns_empty(self):
        assert validate_workflow_state(_VALID_DATA) == []

    def test_missing_required_field(self):
        data = {k: v for k, v in _VALID_DATA.items() if k != "mode"}
        errors = validate_workflow_state(data)
        assert any("mode" in e for e in errors)

    def test_invalid_current_state(self):
        data = {**_VALID_DATA, "current_state": "Invalid"}
        errors = validate_workflow_state(data)
        assert any("current_state" in e for e in errors)

    def test_empty_current_phase_allowed(self):
        data = {**_VALID_DATA, "current_phase": ""}
        assert validate_workflow_state(data) == []

    def test_executing_session_keeps_empty_current_phase(self, tmp_path: Path):
        """Orchestrator keeps current_phase empty during Executing; task-runner owns phases in code-log."""
        p = tmp_path / "workflow-state.md"
        save_workflow_state(
            p,
            {
                **_VALID_DATA,
                "current_state": "Executing",
                "current_task": "t1",
                "current_phase": "",
            },
        )
        loaded = load_workflow_state(p)
        assert loaded["current_phase"] == ""

    def test_invalid_current_phase(self):
        data = {**_VALID_DATA, "current_phase": "NotAPhase"}
        errors = validate_workflow_state(data)
        assert any("current_phase" in e for e in errors)


class TestSaveLoadRoundTrip:
    def test_round_trip(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        save_workflow_state(p, _VALID_DATA)
        loaded = load_workflow_state(p)
        for key in _REQUIRED_FIELD_NAMES:
            if key == "updated_at":
                assert loaded[key]
            else:
                assert loaded[key] == _VALID_DATA[key]

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = tmp_path / "s1" / "workflow-state.md"
        save_workflow_state(p, _VALID_DATA)
        assert p.exists()


class TestMerge:
    def test_partial_save_preserves_historical(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        _write_valid(p, historical="true")
        save_workflow_state(p, {"current_state": "Closing"})
        loaded = load_workflow_state(p)
        assert loaded["historical"] == "true"
        assert loaded["current_state"] == "Closing"

    def test_partial_save_preserves_extra_keys(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        _write_valid(p, custom_flag="yes")
        save_workflow_state(p, {"current_task": "t2"})
        loaded = load_workflow_state(p)
        assert loaded["custom_flag"] == "yes"
        assert loaded["current_task"] == "t2"


class TestInitPreparing:
    def test_defaults(self, tmp_path: Path):
        p = tmp_path / "s1" / "workflow-state.md"
        init_preparing(p, mode="work-order", task_list_ref="/ref/list.md")
        loaded = load_workflow_state(p)
        assert loaded["current_state"] == "Preparing"
        assert loaded["mode"] == "work-order"
        assert loaded["task_list_ref"] == "/ref/list.md"
        assert loaded["current_task"] == ""
        assert loaded["current_phase"] == ""


class TestMarkHistorical:
    def test_injects_historical_on_legacy_partial_frontmatter(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        p.write_text(
            "---\ncurrent_state: Delivered\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        mark_historical(p)
        loaded = load_workflow_state(p)
        assert loaded["historical"] == "true"
        assert loaded["current_state"] == "Delivered"

    def test_injects_historical(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        _write_valid(p, current_state="Delivered")
        mark_historical(p)
        loaded = load_workflow_state(p)
        assert loaded["historical"] == "true"

    def test_idempotent(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        _write_valid(p, current_state="Delivered", historical="true")
        mark_historical(p)
        loaded = load_workflow_state(p)
        assert loaded["historical"] == "true"

    def test_missing_file_no_op(self, tmp_path: Path):
        mark_historical(tmp_path / "missing.md")


class TestResolveWorkflowStatePath:
    def test_resolves_from_session_state(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle-id"
        code_dir = cycle_dir / "tech" / "code"
        code_dir.mkdir(parents=True)
        (code_dir / "session-state.md").write_text(
            "---\nversion: 1\nactive_session: 2\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        (code_dir / "s2").mkdir()
        (code_dir / "s2" / "workflow-state.md").write_text(
            "---\n"
            "version: 1\n"
            "workflow: tech-code\n"
            "current_state: Preparing\n"
            "mode: \n"
            "task_list_ref: \n"
            "current_task: \n"
            "current_phase: \n"
            "updated_at: 2024-01-01T00:00:00+00:00\n"
            "---\n",
            encoding="utf-8",
        )
        assert resolve_workflow_state_path(cycle_dir) == code_dir / "s2" / "workflow-state.md"


class TestNegativeCases:
    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            load_workflow_state(tmp_path / "missing.md")

    def test_missing_frontmatter_raises(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        p.write_text("# no frontmatter\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            load_workflow_state(p)

    def test_broken_frontmatter_raises(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        p.write_text("---\nno closing delimiter\n", encoding="utf-8")
        with pytest.raises(ValueError, match="empty or invalid frontmatter"):
            load_workflow_state(p)


class TestCLI:
    def test_schema_flag_outputs_valid_json(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--schema"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) >= len(_REQUIRED_FIELD_NAMES)

    def test_read_flag(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        _write_valid(p)
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--read", "--path", str(p)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["current_state"] == "Executing"

    def test_read_cycle_dir(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle-id"
        code_dir = cycle_dir / "tech" / "code"
        code_dir.mkdir(parents=True)
        (code_dir / "session-state.md").write_text(
            "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        _write_valid(code_dir / "s1" / "workflow-state.md")
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--read", "--cycle-dir", str(cycle_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["workflow"] == "tech-code"

    def test_write_flag(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        payload = json.dumps(_VALID_DATA)
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--write", "--path", str(p), "--json", payload],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert load_workflow_state(p)["current_state"] == "Executing"

    def test_write_invalid_json_exits_nonzero(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--write", "--path", str(p), "--json", "not-json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_write_validation_error_exits_nonzero(self, tmp_path: Path):
        p = tmp_path / "workflow-state.md"
        payload = json.dumps({"version": "1"})
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--write", "--path", str(p), "--json", payload],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
