#!/usr/bin/env python3
"""Tests for session_state_schema.py."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

from session_state_schema import (
    bump_active_doc,
    get_schema,
    load_active_doc,
    load_active_doc_from_cycle,
    next_doc_round,
    resolve_path,
    save_active_doc,
)
from workflow_common import CACHE_DIR, CACHE_SUBDIR

_REQUIRED_FIELD_NAMES = {"version", "active_doc", "updated_at"}
_CYCLE_ID = "feat-test-session-state"


def _write_session_state(path: Path, active_doc: int) -> None:
    path.write_text(
        f"---\nversion: 1\nactive_doc: {active_doc}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _seed_cycle(tmp_path: Path, *, active_doc: Optional[int] = None) -> Path:
    base = tmp_path / CACHE_DIR / _CYCLE_ID / CACHE_SUBDIR
    base.mkdir(parents=True, exist_ok=True)
    if active_doc is not None:
        _write_session_state(base / "session-state.md", active_doc)
    return tmp_path


class TestGetSchema:
    def test_contains_all_required_fields(self):
        schema = get_schema()
        field_names = {s["field"] for s in schema}
        assert _REQUIRED_FIELD_NAMES.issubset(field_names)

    def test_required_fields_marked_required(self):
        for entry in get_schema():
            if entry["field"] in _REQUIRED_FIELD_NAMES:
                assert entry["required"] is True

    def test_returns_copy(self):
        s1 = get_schema()
        s2 = get_schema()
        s1.clear()
        assert len(s2) > 0


class TestLoadActiveDoc:
    def test_reads_active_doc(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 2)
        assert load_active_doc(p) == 2

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            load_active_doc(tmp_path / "missing.md")

    def test_missing_file_with_default(self, tmp_path: Path):
        assert load_active_doc(tmp_path / "missing.md", default=1) == 1

    def test_missing_field_raises(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nversion: 1\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="active_doc"):
            load_active_doc(p)

    def test_missing_field_with_default(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nversion: 1\n---\n", encoding="utf-8")
        assert load_active_doc(p, default=1) == 1

    def test_invalid_value_with_default(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nactive_doc: bad\n---\n", encoding="utf-8")
        assert load_active_doc(p, default=1) == 1


class TestLoadActiveDocFromCycle:
    def test_reads_from_cycle(self, tmp_path: Path):
        _seed_cycle(tmp_path, active_doc=3)
        assert load_active_doc_from_cycle(_CYCLE_ID, tmp_path) == 3

    def test_missing_file_defaults_to_one(self, tmp_path: Path):
        _seed_cycle(tmp_path)
        assert load_active_doc_from_cycle(_CYCLE_ID, tmp_path) == 1


class TestSaveActiveDoc:
    def test_round_trip(self, tmp_path: Path):
        p = tmp_path / "sub" / "session-state.md"
        save_active_doc(p, 3)
        assert load_active_doc(p) == 3

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = tmp_path / "a" / "b" / "session-state.md"
        save_active_doc(p, 1)
        assert p.exists()


class TestNextDocRound:
    def test_absent_file_returns_one(self, tmp_path: Path):
        assert next_doc_round(tmp_path / "session-state.md") == 1

    def test_existing_increments(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 1)
        assert next_doc_round(p) == 2

    def test_missing_active_doc_increments_from_zero(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nversion: 1\n---\n", encoding="utf-8")
        assert next_doc_round(p) == 1


class TestBumpActiveDoc:
    def test_creates_first_round(self, tmp_path: Path):
        _seed_cycle(tmp_path)
        assert bump_active_doc(_CYCLE_ID, tmp_path) == 1
        assert load_active_doc_from_cycle(_CYCLE_ID, tmp_path) == 1

    def test_increments_existing_round(self, tmp_path: Path):
        _seed_cycle(tmp_path, active_doc=2)
        assert bump_active_doc(_CYCLE_ID, tmp_path) == 3
        assert load_active_doc_from_cycle(_CYCLE_ID, tmp_path) == 3


class TestResolvePath:
    def test_points_to_session_state(self, tmp_path: Path):
        expected = tmp_path / CACHE_DIR / _CYCLE_ID / CACHE_SUBDIR / "session-state.md"
        assert resolve_path(_CYCLE_ID, tmp_path) == expected


class TestCLI:
    def test_schema_flag_outputs_valid_json(self):
        script = CORE / "session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) >= len(_REQUIRED_FIELD_NAMES)

    def test_read_flag_with_path(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 4)
        script = CORE / "session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--read", "--path", str(p)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "4"

    def test_read_flag_with_cycle_id(self, tmp_path: Path):
        _seed_cycle(tmp_path, active_doc=5)
        script = CORE / "session_state_schema.py"
        result = subprocess.run(
            [
                sys.executable, str(script),
                "--read",
                "--cycle-id", _CYCLE_ID,
                "--project-root", str(tmp_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "5"

    def test_next_flag_with_path(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 1)
        script = CORE / "session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--next", "--path", str(p)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "2"
        assert load_active_doc(p) == 2

    def test_next_flag_with_cycle_id(self, tmp_path: Path):
        _seed_cycle(tmp_path, active_doc=2)
        script = CORE / "session_state_schema.py"
        result = subprocess.run(
            [
                sys.executable, str(script),
                "--next",
                "--cycle-id", _CYCLE_ID,
                "--project-root", str(tmp_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "3"
        assert load_active_doc_from_cycle(_CYCLE_ID, tmp_path) == 3
