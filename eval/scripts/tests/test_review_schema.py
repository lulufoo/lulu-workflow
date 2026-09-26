#!/usr/bin/env python3
"""Tests for the ReviewFile v3 data contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from review_schema import (  # noqa: E402
    get_schema,
    resolve_handling_mode,
    validate_issue_row,
    validate_issue_transition,
    validate_probe_finding,
    validate_review_content,
)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "e2-1",
        "root_cause": "WO-ERROR",
        "handling_mode": "direct",
        "sot_ref": "—",
        "location": "target §3",
        "severity": "critical",
        "evidence": "bad API",
        "description": "wrong API",
        "status": "pending",
        "decision": "—",
        "resolution": "",
    }
    row.update(overrides)
    return row


def _content(row: str = "") -> str:
    return (
        "---\n"
        "schema_version: 3\n"
        "dimension_id: synthetic-quality\n"
        "round_token: round-1\n"
        "---\n\n"
        "# Review\n\n"
        "| ID | root_cause | handling_mode | sot_ref | location | severity | evidence "
        "| description | status | decision | resolution |\n"
        "|----|------------|---------------|---------|----------|----------|----------"
        "|-------------|--------|----------|------------|\n"
        f"{row}"
    )


class TestSchema:
    def test_v3_has_required_frontmatter_and_eleven_columns(self):
        schema = get_schema()
        assert schema["version"] == "3"
        assert schema["required_frontmatter"] == [
            "schema_version",
            "dimension_id",
            "round_token",
        ]
        assert len(schema["columns"]) == 11
        assert schema["columns"][2] == "handling_mode"

    @pytest.mark.parametrize(
        ("policy", "root_cause", "expected"),
        [
            ("class-default", "WO-MISS", "direct"),
            ("class-default", "WO-ERROR", "direct"),
            ("class-default", "DECISION-REQUIRED", "human-gated"),
            ("class-default", "SOT-DEFECT", "human-gated"),
            ("human-first", "WO-MISS", "human-gated"),
            ("human-first", "SOT-DEFECT", "human-gated"),
        ],
    )
    def test_handling_mode_mapping(
        self,
        policy: str,
        root_cause: str,
        expected: str,
    ):
        assert resolve_handling_mode(policy, root_cause) == expected

    def test_probe_payload_must_not_supply_handling_mode(self):
        errors = validate_probe_finding({
            "id": "e2-1",
            "root_cause": "WO-ERROR",
            "handling_mode": "direct",
        })
        assert "probe finding must not include handling_mode" in errors


class TestIssueRows:
    @pytest.mark.parametrize("handling_mode", ["direct", "human-gated"])
    def test_pending_issue_is_valid(self, handling_mode: str):
        assert validate_issue_row(_row(handling_mode=handling_mode), phase="probe") == []

    @pytest.mark.parametrize(
        "status",
        ["approved", "fixed", "accepted-divergence", "ignored", "escalated", "reclassified"],
    )
    def test_result_shaped_statuses_are_rejected(self, status: str):
        errors = validate_issue_row(
            _row(status=status, decision="fix", resolution="done"),
            phase="remediation",
        )
        assert any("invalid status" in error for error in errors)

    @pytest.mark.parametrize(
        "decision",
        ["fix", "accept-divergence", "select", "allow-multiple", "escalate"],
    )
    def test_resolved_issue_accepts_target_decisions(self, decision: str):
        assert validate_issue_row(
            _row(
                handling_mode="human-gated",
                status="resolved",
                decision=decision,
                resolution="recorded result",
            ),
            phase="remediation",
        ) == []

    def test_pending_requires_em_dash_and_empty_resolution(self):
        assert validate_issue_row(_row(), phase="probe") == []
        assert any(
            "pending decision" in error
            for error in validate_issue_row(_row(decision="fix"), phase="probe")
        )
        assert any(
            "pending resolution" in error
            for error in validate_issue_row(_row(resolution="premature"), phase="probe")
        )

    def test_resolved_requires_decision_and_resolution(self):
        errors = validate_issue_row(
            _row(status="resolved", decision="—"),
            phase="remediation",
        )
        assert any("resolved decision" in error for error in errors)
        assert any("resolved resolution" in error for error in errors)

    def test_published_handling_mode_is_immutable(self):
        before = _row(handling_mode="direct")
        after = copy.deepcopy(before)
        after["handling_mode"] = "human-gated"
        assert validate_issue_transition(before, after) == [
            "e2-1: handling_mode is immutable",
        ]


class TestReviewDocument:
    def test_valid_v3_document(self):
        row = (
            "| e2-1 | WO-ERROR | direct | — | loc | minor | ev | desc "
            "| pending | — | |\n"
        )
        assert validate_review_content(_content(row)) == []

    def test_shared_template_declares_v3_identity_and_handling_mode(self):
        template = (
            Path(__file__).resolve().parents[2] / "review.template.md"
        ).read_text(encoding="utf-8")
        assert template.startswith("---\nschema_version: 3\n")
        assert "dimension_id: {{DIMENSION_ID}}" in template
        assert "round_token: {{ROUND_TOKEN}}" in template
        assert "| ID | root_cause | handling_mode |" in template

    @pytest.mark.parametrize(
        "frontmatter",
        [
            "",
            "---\ndimension_id: synthetic-quality\nround_token: round-1\n---\n",
            "---\nschema_version: 2\ndimension_id: synthetic-quality\nround_token: round-1\n---\n",
        ],
    )
    def test_legacy_review_is_stably_rejected(self, frontmatter: str):
        content = _content()
        content = frontmatter + content.split("---\n", 2)[-1]
        assert any(
            "incompatible_round" in error
            for error in validate_review_content(content)
        )
