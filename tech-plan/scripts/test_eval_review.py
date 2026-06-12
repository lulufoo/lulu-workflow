#!/usr/bin/env python3
"""Tests for eval_review.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_review import compute_fix_severity  # noqa: E402


class TestComputeFixSeverity:
    def test_highest_severity_wins(self):
        issues = [
            {
                "id": "e2-1",
                "severity": "critical",
                "description": "missing error handling",
                "decision": "fix",
            },
            {
                "id": "e2-2",
                "severity": "minor",
                "description": "naming",
                "decision": "ignore",
            },
        ]
        severity, reason = compute_fix_severity(issues)
        assert severity == "critical"
        assert reason == "e2-1: missing error handling"

    def test_all_ignored_uses_minor(self):
        issues = [
            {
                "id": "e2-1",
                "severity": "critical",
                "description": "missing error handling",
                "decision": "ignore",
            },
        ]
        severity, reason = compute_fix_severity(issues)
        assert severity == "minor"
        assert reason == "e2-1: missing error handling"

    def test_no_issues_defaults_minor(self):
        severity, reason = compute_fix_severity([])
        assert severity == "minor"
        assert reason == ""
