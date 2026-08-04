#!/usr/bin/env python3
"""Tests for eval/scripts/review_io.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import review_io  # noqa: E402
from review_io import (  # noqa: E402
    has_pending_human,
    issues_by_root_cause,
    parse_review_file,
    pending_artifact_rows,
    pending_human_rows,
)

_REVIEW_HEADER = (
    "# Tech Review — E2 | revision1 round 1\n\n"
    "**Date:** 2026-01-01\n"
    "**Refs:** codebase\n\n"
    "| ID | root_cause | sot_ref | location | severity | evidence "
    "| description | status | decision | resolution |\n"
    "|----|------------|---------|----------|----------|----------"
    "|-------------|--------|----------|------------|\n"
)


def _write_review(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "tech-review-e12.md"
    path.write_text(_REVIEW_HEADER + rows, encoding="utf-8")
    return path


class TestParseReviewFile:
    def test_parses_resolution_column(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-ERROR | — | tech-doc §3 | critical | bad API | "
            "wrong API | pending | — | decision applied |\n",
        )
        rows = parse_review_file(path)
        assert len(rows) == 1
        assert rows[0]["id"] == "e2-1"
        assert rows[0]["root_cause"] == "WO-ERROR"
        assert rows[0]["severity"] == "critical"
        assert rows[0]["resolution"] == "decision applied"

    def test_empty_data_rows(self, tmp_path: Path):
        path = _write_review(tmp_path, "")
        assert parse_review_file(path) == []


class TestFilterRows:
    def test_pending_artifact_rows(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-MISS | product §1 | tech-doc §2 | medium | gap | "
            "missing | pending | — | |\n"
            "| e2-2 | SOT-DEFECT | product §1 | tech-doc §2 | medium | gap | "
            "ambiguous | pending | — | |\n"
            "| e2-3 | DECISION-REQUIRED | product §2 | tech-doc §4 | critical | "
            "two valid readings | human choice required | pending | — | |\n",
        )
        rows = parse_review_file(path)
        assert len(pending_artifact_rows(rows)) == 1
        assert len(pending_human_rows(rows)) == 2
        assert has_pending_human(rows)

    def test_old_sot_names_are_unavailable(self):
        assert not hasattr(review_io, "_SOT_LABELS")
        assert not hasattr(review_io, "pending_sot_rows")
        assert not hasattr(review_io, "has_pending_sot")

    def test_issues_by_root_cause(self, tmp_path: Path):
        path = _write_review(
            tmp_path,
            "| e2-1 | WO-ERROR | — | loc | minor | ev | desc | pending | — | |\n",
        )
        rows = parse_review_file(path)
        filtered = issues_by_root_cause(rows, frozenset({"WO-ERROR"}))
        assert len(filtered) == 1
