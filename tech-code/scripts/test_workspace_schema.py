#!/usr/bin/env python3
"""Tests for workspace_schema.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workspace_schema import get_schema, load_workspace, save_workspace, validate_workspace


_REQUIRED_FIELD_NAMES = {"worktree_path", "project_root", "primary_repo", "branch", "created_at"}

_VALID_DATA = {
    "worktree_path": "/abs/path/wt/",
    "project_root": "/abs/path/project",
    "primary_repo": "owner/repo",
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
        script = Path(__file__).resolve().parent / "workspace_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) >= len(_REQUIRED_FIELD_NAMES)
