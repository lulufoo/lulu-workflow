#!/usr/bin/env python3
"""Tests for ReviewFile v3 parsing and filtering."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from review_io import (  # noqa: E402
    count_resolved,
    has_escalated,
    parse_review_content,
    parse_review_frontmatter,
    pending_rows,
    rows_by_handling_mode,
)


def _review(rows: str) -> str:
    return (
        "---\n"
        "schema_version: 3\n"
        "dimension_id: synthetic-quality\n"
        "round_token: round-1\n"
        "---\n\n"
        "| ID | root_cause | handling_mode | sot_ref | location | severity | evidence "
        "| description | status | decision | resolution |\n"
        "|----|------------|---------------|---------|----------|----------|----------"
        "|-------------|--------|----------|------------|\n"
        f"{rows}"
    )


def test_parses_frontmatter_and_handling_mode():
    content = _review(
        "| e2-1 | WO-ERROR | direct | — | loc | critical | ev | desc "
        "| pending | — | |\n",
    )
    assert parse_review_frontmatter(content) == {
        "schema_version": "3",
        "dimension_id": "synthetic-quality",
        "round_token": "round-1",
    }
    assert parse_review_content(content)[0]["handling_mode"] == "direct"
    assert parse_review_content(
        content,
        expected_dimension_id="synthetic-quality",
        expected_round_token="round-1",
    )[0]["id"] == "e2-1"


def test_filters_by_persisted_handling_mode_not_policy_or_root_cause():
    rows = parse_review_content(_review(
        "| e2-1 | WO-ERROR | human-gated | — | loc | medium | ev | desc "
        "| pending | — | |\n"
        "| e2-2 | SOT-DEFECT | human-gated | sot | loc | critical | ev | desc "
        "| pending | — | |\n"
        "| e2-3 | WO-MISS | direct | sot | loc | medium | ev | desc "
        "| resolved | fix | fixed |\n",
    ))
    assert [row["id"] for row in rows_by_handling_mode(rows, "human-gated")] == [
        "e2-1",
        "e2-2",
    ]
    assert [row["id"] for row in pending_rows(rows)] == ["e2-1", "e2-2"]
    assert count_resolved(rows) == 1


def test_escalation_is_a_decision_not_a_status():
    rows = parse_review_content(_review(
        "| e2-1 | SOT-DEFECT | human-gated | sot | loc | critical | ev | desc "
        "| resolved | escalate | upstream decision required |\n",
    ))
    assert has_escalated(rows)


def test_parser_rejects_legacy_review_before_reading_business_rows():
    legacy = (
        "| ID | root_cause | status | decision |\n"
        "|----|------------|--------|----------|\n"
        "| old-1 | WO-ERROR | fixed | fix |\n"
    )
    with pytest.raises(ValueError, match="incompatible_round"):
        parse_review_content(legacy)


def test_parser_rejects_reordered_v3_header():
    content = _review("").replace(
        "| ID | root_cause | handling_mode |",
        "| root_cause | ID | handling_mode |",
    )
    with pytest.raises(ValueError, match="header"):
        parse_review_content(content)


@pytest.mark.parametrize(
    "row",
    [
        "| e2-1 | WO-ERROR | direct | — | loc | critical | ev | desc | pending | — |\n",
        "| e2-1 | WO-ERROR | direct | — | loc | critical | ev | desc | pending | — | | extra |\n",
    ],
)
def test_parser_rejects_rows_with_nonexact_cell_count(row: str):
    with pytest.raises(ValueError, match="11 cells"):
        parse_review_content(_review(row))


def test_parser_rejects_legacy_id_and_description_aliases():
    content = _review(
        "| e2-1 | WO-ERROR | direct | — | loc | critical | ev | desc "
        "| pending | — | |\n",
    ).replace("| ID |", "| # |").replace("| description |", "| issue |")
    with pytest.raises(ValueError, match="header"):
        parse_review_content(content)


@pytest.mark.parametrize("missing", ["dimension_id", "round_token"])
def test_parser_requires_complete_v3_identity(missing: str):
    content = _review("").replace(
        f"{missing}: "
        + ("synthetic-quality" if missing == "dimension_id" else "round-1")
        + "\n",
        "",
    )
    with pytest.raises(ValueError, match=missing):
        parse_review_content(content)


@pytest.mark.parametrize(
    ("expected_dimension_id", "expected_round_token", "mismatch"),
    [
        ("other-dimension", "round-1", "dimension_id"),
        ("synthetic-quality", "other-round", "round_token"),
    ],
)
def test_parser_rejects_expected_identity_mismatch_before_rows(
    expected_dimension_id: str,
    expected_round_token: str,
    mismatch: str,
):
    malformed_row = (
        "| too | few | cells |\n"
    )
    with pytest.raises(ValueError, match=mismatch):
        parse_review_content(
            _review(malformed_row),
            expected_dimension_id=expected_dimension_id,
            expected_round_token=expected_round_token,
        )
