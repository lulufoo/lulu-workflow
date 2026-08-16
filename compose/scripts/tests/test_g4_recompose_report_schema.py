#!/usr/bin/env python3
"""Tests for the G4 internal-audit report schema."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from g4_recompose_report_schema import (  # noqa: E402
    check_report_readable,
    normalize_report,
    validate_report,
)


def _clean_report(**overrides) -> dict:
    base = {
        "version": 1,
        "facts_digest": "a" * 64,
        "opens_digest": "b" * 64,
        "findings": [],
        "buildable": True,
        "reversible": True,
        "verifiable": True,
        "evidence": {
            "buildable": "facts compose a buildable set",
            "reversible": "consequential actions have reversal paths",
            "verifiable": "settled claims have observable checks",
        },
        "produced_by": "subagent",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_validate_report_requires_integer_version_1() -> None:
    errors = validate_report(_clean_report(version="1"))
    assert any("version" in item for item in errors)


def test_empty_findings_valid_only_when_all_predicates_true() -> None:
    assert validate_report(_clean_report()) == []
    errors = validate_report(_clean_report(buildable=False))
    assert any("findings" in item or "buildable" in item for item in errors)


def test_nonempty_findings_allowed_when_a_predicate_is_false() -> None:
    errors = validate_report(
        _clean_report(
            findings=[
                {
                    "question": "Who owns retry?",
                    "basis": "Two facts disagree",
                    "blocking": True,
                }
            ],
            buildable=False,
        )
    )
    assert errors == []


def test_finding_requires_question_basis_blocking() -> None:
    errors = validate_report(
        _clean_report(
            findings=[{"question": "", "basis": "x", "blocking": True}],
            buildable=False,
        )
    )
    assert any("question" in item for item in errors)


def test_rejects_legacy_section_and_shape_fields() -> None:
    errors = validate_report(
        _clean_report(
            conflicts=[],
            reforms_shape=True,
            shape_absorbed=True,
            facts=["do not copy facts"],
        )
    )
    joined = " ".join(errors)
    assert "conflicts" in joined or "reforms_shape" in joined or "facts" in joined


def test_finding_rejects_sections_and_owning_section() -> None:
    errors = validate_report(
        _clean_report(
            findings=[
                {
                    "question": "Who owns retry?",
                    "basis": "Two facts disagree",
                    "blocking": True,
                    "sections": ["I", "ST"],
                    "owning_section": "I",
                }
            ],
            buildable=False,
        )
    )
    joined = " ".join(errors)
    assert "sections" in joined or "owning_section" in joined


def test_normalize_and_check_closable_clean_report() -> None:
    report = normalize_report(_clean_report())
    result = check_report_readable(report)
    assert result["schema_ok"] is True
    assert result["closable"] is True
    assert result["findings"] == []


def test_check_not_closable_when_findings_remain() -> None:
    report = normalize_report(
        _clean_report(
            findings=[
                {
                    "question": "Who owns retry?",
                    "basis": "Two facts disagree",
                    "blocking": True,
                }
            ],
            buildable=False,
        )
    )
    result = check_report_readable(report)
    assert result["schema_ok"] is True
    assert result["closable"] is False
    assert len(result["findings"]) == 1
