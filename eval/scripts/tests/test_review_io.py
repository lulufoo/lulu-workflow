#!/usr/bin/env python3
"""Tests for eval/scripts/review_io.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_io import (  # noqa: E402
    issues_by_root_cause,
    parse_review_file,
    pending_artifact_rows,
    pending_sot_rows,
)

_REVIEW_HEADER = (
    "# Tech Review — E2 | revision1 round 1\n\n"
    "**Date:** 2026-01-01\n"
    "**Refs:** codebase\n\n"
    "| ID | root_cause | sot_ref | location | severity | evidence "
    "| description | status | decision |\n"
    "|----|------------|---------|----------|----------|----------"
    "|-------------|--------|----------|\n"
)


def _write_review(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "tech-review-e12.md"
    path.write_text(_REVIEW_HEADER + rows, encoding="utf-8")
    return path


class TestParseReviewFile:
    def test_parses_nine_column_rows(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | bad API | "
            "wrong API | pending | — |\n",
        )
        rows = parse_review_file(path)
        assert len(rows) == 1
        assert rows[0]["id"] == "e2-1"
        assert rows[0]["root_cause"] == "WO-ERROR"
        assert rows[0]["severity"] == "critical"

    def test_empty_data_rows(self, tmp_path: Path):
        path = _write_review(tmp_path, "")
        assert parse_review_file(path) == []


class TestFilterRows:
    def test_pending_artifact_rows(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-MISS | product §1 | tech-doc §2 | medium | gap | "
            "missing | pending | — |\n"
            "| e2-2 | SOT-DEFECT | product §1 | tech-doc §2 | medium | gap | "
            "ambiguous | pending | — |\n",
        )
        rows = parse_review_file(path)
        assert len(pending_artifact_rows(rows)) == 1
        assert len(pending_sot_rows(rows)) == 1

    def test_issues_by_root_cause(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-ERROR | — | loc | minor | ev | desc | pending | — |\n",
        )
        rows = parse_review_file(path)
        filtered = issues_by_root_cause(rows, frozenset({"WO-ERROR"}))
        assert len(filtered) == 1
