#!/usr/bin/env python3
"""Tests for session_state_schema.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_session_state_schema import (
    get_schema,
    load_session_state,
    load_work_order_round,
    next_session_round,
    save_session_state,
)


_REQUIRED_FIELD_NAMES = {"version", "active_session", "updated_at"}


def _write_session_state(path: Path, active_session: int) -> None:
    path.write_text(
        f"---\nversion: 1\nactive_session: {active_session}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


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


class TestLoadSessionState:
    def test_reads_active_session(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 2)
        assert load_session_state(p) == 2

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            load_session_state(tmp_path / "missing.md")

    def test_missing_field_raises(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nversion: 1\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="active_session"):
            load_session_state(p)


class TestSaveSessionState:
    def test_round_trip(self, tmp_path: Path):
        p = tmp_path / "sub" / "session-state.md"
        save_session_state(p, 3)
        assert load_session_state(p) == 3

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = tmp_path / "a" / "b" / "session-state.md"
        save_session_state(p, 1)
        assert p.exists()


class TestNextSessionRound:
    def test_absent_file_returns_one(self, tmp_path: Path):
        assert next_session_round(tmp_path / "session-state.md") == 1

    def test_existing_increments(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 1)
        assert next_session_round(p) == 2


class TestLoadWorkOrderRound:
    def test_prefers_active_doc(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nactive_doc: 3\nactive_session: 9\n---\n", encoding="utf-8")
        assert load_work_order_round(p) == "3"

    def test_fallback_to_active_session(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nactive_session: 2\n---\n", encoding="utf-8")
        assert load_work_order_round(p) == "2"

    def test_missing_fields_raises(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        p.write_text("---\nversion: 1\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="active_doc/active_session"):
            load_work_order_round(p)


class TestCLI:
    def test_schema_flag_outputs_valid_json(self):
        script = Path(__file__).resolve().parents[1] / "tc_session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) >= len(_REQUIRED_FIELD_NAMES)

    def test_read_flag(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 4)
        script = Path(__file__).resolve().parents[1] / "tc_session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--read", "--path", str(p)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "4"

    def test_next_flag(self, tmp_path: Path):
        p = tmp_path / "session-state.md"
        _write_session_state(p, 1)
        script = Path(__file__).resolve().parents[1] / "tc_session_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--next", "--path", str(p)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "2"
        assert load_session_state(p) == 2
