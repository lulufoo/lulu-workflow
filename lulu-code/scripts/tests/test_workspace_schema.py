#!/usr/bin/env python3
"""Tests for workspace_schema.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_workspace_schema import (
    assess_workspace_file,
    get_schema,
    load_workspace,
    read_workspace_file,
    save_workspace,
    validate_workspace,
    validate_workspace_semantic,
)


_REQUIRED_FIELD_NAMES = {"worktree_path", "project_root", "branch", "created_at"}

_VALID_DATA = {
    "worktree_path": "/abs/path/wt/",
    "project_root": "/abs/path/project",
    "branch": "wt/feat-slug",
    "created_at": "2024-01-01T00:00:00+00:00",
}


class TestGetSchema:
    def test_contains_all_required_fields(self):
        schema = get_schema()
        field_names = {s["field"] for s in schema}
        assert _REQUIRED_FIELD_NAMES.issubset(field_names)

    def test_required_fields_marked_required(self):
        schema = get_schema()
        for entry in schema:
            if entry["field"] in _REQUIRED_FIELD_NAMES:
                assert entry["required"] is True

    def test_extra_worktrees_is_optional(self):
        schema = get_schema()
        extra = next(s for s in schema if s["field"] == "extra_worktrees")
        assert extra["required"] is False

    def test_returns_copy(self):
        s1 = get_schema()
        s2 = get_schema()
        s1.clear()
        assert len(s2) > 0


class TestValidateWorkspace:
    def test_valid_data_returns_empty(self):
        assert validate_workspace(_VALID_DATA) == []

    def test_missing_required_field(self):
        data = {k: v for k, v in _VALID_DATA.items() if k != "worktree_path"}
        errors = validate_workspace(data)
        assert any("worktree_path" in e for e in errors)

    def test_missing_multiple_fields(self):
        errors = validate_workspace({})
        assert len(errors) == len(_REQUIRED_FIELD_NAMES)

    def test_extra_field_allowed(self):
        data = {**_VALID_DATA, "extra_field": "value"}
        assert validate_workspace(data) == []


class TestLoadWorkspace:
    def test_valid_file_returns_data(self, tmp_path):
        p = tmp_path / "workspace.json"
        p.write_text(json.dumps(_VALID_DATA), encoding="utf-8")
        result = load_workspace(p)
        assert result["worktree_path"] == _VALID_DATA["worktree_path"]

    def test_missing_required_field_raises(self, tmp_path):
        p = tmp_path / "workspace.json"
        data = {k: v for k, v in _VALID_DATA.items() if k != "branch"}
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="branch"):
            load_workspace(p)


class TestSaveWorkspace:
    def test_writes_valid_json(self, tmp_path):
        p = tmp_path / "sub" / "workspace.json"
        save_workspace(p, _VALID_DATA)
        assert p.exists()
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert loaded == _VALID_DATA

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "workspace.json"
        save_workspace(p, _VALID_DATA)
        assert p.exists()


class TestCLI:
    def test_schema_flag_outputs_valid_json(self):
        script = Path(__file__).resolve().parents[1] / "tc_workspace_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) >= len(_REQUIRED_FIELD_NAMES)


class TestReadWorkspaceFile:
    def test_valid_json(self, tmp_path):
        p = tmp_path / "workspace.json"
        p.write_text(json.dumps(_VALID_DATA), encoding="utf-8")
        data, errors = read_workspace_file(p)
        assert errors == []
        assert data == _VALID_DATA

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "workspace.json"
        p.write_text("{not json", encoding="utf-8")
        data, errors = read_workspace_file(p)
        assert data is None
        assert len(errors) == 1
        assert "invalid JSON" in errors[0]

    def test_non_object_root(self, tmp_path):
        p = tmp_path / "workspace.json"
        p.write_text("[1, 2]", encoding="utf-8")
        data, errors = read_workspace_file(p)
        assert data is None
        assert errors == ["root must be a JSON object"]


class TestValidateWorkspaceSemantic:
    def test_valid_data(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {**_VALID_DATA, "project_root": str(project_root.resolve())}
        assert validate_workspace_semantic(data, project_root) == []

    def test_project_root_mismatch(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {**_VALID_DATA, "project_root": "/other/path"}
        errors = validate_workspace_semantic(data, project_root)
        assert any("project_root mismatch" in e for e in errors)

    def test_worktree_path_not_absolute(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {
            **_VALID_DATA,
            "project_root": str(project_root.resolve()),
            "worktree_path": "rel/path/",
        }
        errors = validate_workspace_semantic(data, project_root)
        assert any("absolute" in e for e in errors)

    def test_worktree_path_no_trailing_slash(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {
            **_VALID_DATA,
            "project_root": str(project_root.resolve()),
            "worktree_path": "/abs/path/wt",
        }
        errors = validate_workspace_semantic(data, project_root)
        assert any("trailing slash" in e for e in errors)

    def test_extra_worktrees_missing_fields(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {
            **_VALID_DATA,
            "project_root": str(project_root.resolve()),
            "extra_worktrees": {"repo-b": {"path": "/abs/extra/"}},
        }
        errors = validate_workspace_semantic(data, project_root)
        assert any("missing 'branch'" in e for e in errors)


class TestAssessWorkspaceFile:
    def test_valid_file(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {
            **_VALID_DATA,
            "project_root": str(project_root.resolve()),
            "worktree_path": "/abs/path/wt/",
        }
        p = tmp_path / "workspace.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        ok, result, errors = assess_workspace_file(p, project_root)
        assert ok is True
        assert errors == []
        assert result["branch"] == data["branch"]

    def test_missing_field(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        data = {k: v for k, v in _VALID_DATA.items() if k != "branch"}
        data["project_root"] = str(project_root.resolve())
        p = tmp_path / "workspace.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        ok, result, errors = assess_workspace_file(p, project_root)
        assert ok is False
        assert any("branch" in e for e in errors)

    def test_bad_json(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        p = tmp_path / "workspace.json"
        p.write_text("{bad", encoding="utf-8")
        ok, result, errors = assess_workspace_file(p, project_root)
        assert ok is False
        assert result is None
        assert len(errors) >= 1
