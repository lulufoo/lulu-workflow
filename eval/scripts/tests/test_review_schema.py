#!/usr/bin/env python3
"""Tests for eval/scripts/review_schema.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_io import parse_review_file  # noqa: E402
from review_schema import (  # noqa: E402
    get_schema,
    validate_issue_row,
    validate_review_file,
    validate_review_header,
)

_HEADER_LINES = [
    "# Tech Review — E2 | revision1 round 1",
    "",
    "**Date:** 2026-01-01",
    "**Refs:** codebase",
    "",
    "| ID | root_cause | sot_ref | location | severity | evidence "
    "| description | status | decision |",
    "|----|------------|---------|----------|----------|----------"
    "|-------------|--------|----------|",
]


class TestGetSchema:
    def test_has_nine_columns(self):
        schema = get_schema()
        assert len(schema["columns"]) == 9
        assert "WO-MISS" in schema["enums"]["root_cause"]


class TestValidateReviewHeader:
    def test_valid_header(self):
        assert validate_review_header(_HEADER_LINES) == []

    def test_invalid_header(self):
        bad = list(_HEADER_LINES)
        bad[5] = "| ID | bad | cols |"
        errors = validate_review_header(bad)
        assert errors


class TestValidateIssueRow:
    def test_valid_probe_row(self):
        row = {
            "id": "e2-1",
            "root_cause": "WO-ERROR",
            "sot_ref": "—",
            "location": "tech-doc §3",
            "severity": "critical",
            "evidence": "bad API design",
            "description": "wrong API",
            "status": "pending",
            "decision": "—",
        }
        assert validate_issue_row(row, phase="probe") == []

    def test_sot_ref_required_for_wo_miss(self):
        row = {
            "id": "e1-1",
            "root_cause": "WO-MISS",
            "sot_ref": "",
            "location": "tech-doc §2",
            "severity": "medium",
            "evidence": "gap",
            "description": "missing",
            "status": "pending",
            "decision": "—",
        }
        errors = validate_issue_row(row, phase="probe")
        assert any("sot_ref" in e for e in errors)

    def test_invalid_root_cause(self):
        row = {
            "id": "e2-1",
            "root_cause": "B-SELF",
            "sot_ref": "—",
            "location": "loc",
            "severity": "minor",
            "evidence": "ev",
            "description": "desc",
            "status": "pending",
            "decision": "—",
        }
        errors = validate_issue_row(row, phase="probe")
        assert any("root_cause" in e for e in errors)


class TestValidateReviewFile:
    def test_valid_file(self, tmp_path: Path):
        path = tmp_path / "review.md"
        path.write_text(
            "\n".join(_HEADER_LINES)
            + "\n| e2-1 | WO-ERROR | — | loc | minor | ev | desc | pending | — |\n",
            encoding="utf-8",
        )
        assert validate_review_file(path) == []

    def test_header_only_valid(self, tmp_path: Path):
        path = tmp_path / "review.md"
        path.write_text("\n".join(_HEADER_LINES) + "\n", encoding="utf-8")
        assert validate_review_file(path) == []

    def test_cli_schema(self):
        import subprocess

        script = Path(__file__).resolve().parents[1] / "review_schema.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["version"] == "1"
