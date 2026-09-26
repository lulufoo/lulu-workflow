"""Focused tests for Slice 2A remediation operation contexts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_operation_context import issue_remediation_context  # noqa: E402
from eval_operation_record_schema import (  # noqa: E402
    cancel_operation_record,
    create_remediation_operation_record,
    get_operation_record,
    load_operation_records,
)


def _issue_context(
    tmp_path: Path,
    *,
    dimension_id: str,
    target_path: Path,
) -> dict:
    review_path = tmp_path / f"{dimension_id}.md"
    review_path.write_text(f"review for {dimension_id}", encoding="utf-8")
    return issue_remediation_context(
        operations_path=tmp_path / "eval-operations.json",
        write_staging_dir=tmp_path / "staging",
        target_path=target_path,
        review_path=review_path,
        round_token="round-1",
        dimension_id=dimension_id,
        method={"ref": "method", "focus": "focus"},
        sots=[{"ref": "spec.md"}],
        required_issue_ids=["a-1", "h-1"],
        handling_modes_by_issue={
            "a-1": "direct",
            "h-1": "human-gated",
        },
        allowed_decisions_by_issue={
            "a-1": ["fix"],
            "h-1": ["fix", "accept-divergence", "escalate"],
        },
    )


def test_context_pins_mixed_authorization_and_v4_bases(tmp_path: Path):
    target_path = tmp_path / "target.md"
    target_path.write_text("target", encoding="utf-8")

    context = _issue_context(
        tmp_path,
        dimension_id="quality",
        target_path=target_path,
    )
    record = get_operation_record(
        tmp_path / "eval-operations.json",
        context["operation_token"],
    )

    assert record["operation_kind"] == "remediation"
    assert record["phase"] == "context-open"
    assert record["required_issue_ids"] == ["a-1", "h-1"]
    assert record["handling_modes_by_issue"] == {
        "a-1": "direct",
        "h-1": "human-gated",
    }
    assert record["allowed_decisions_by_issue"]["a-1"] == ["fix"]
    assert record["review_before_exists"] is True
    assert record["target_lease_key"] == target_path.resolve().as_posix()
    assert {
        "status",
        "force_human_resolution",
        "allowed_resolution_kinds",
    }.isdisjoint(record)


def test_open_dimension_context_resumes_same_token_without_writes(tmp_path: Path):
    target_path = tmp_path / "target.md"
    target_path.write_text("target", encoding="utf-8")
    first = _issue_context(
        tmp_path,
        dimension_id="quality",
        target_path=target_path,
    )
    operations_path = tmp_path / "eval-operations.json"
    before = operations_path.read_bytes()

    second = _issue_context(
        tmp_path,
        dimension_id="quality",
        target_path=target_path,
    )

    assert second["operation_token"] == first["operation_token"]
    assert operations_path.read_bytes() == before
    assert len(load_operation_records(operations_path)["operations"]) == 1


def test_shared_target_lease_blocks_other_dimension_until_cancel(tmp_path: Path):
    target_path = tmp_path / "target.md"
    target_path.write_text("target", encoding="utf-8")
    first = _issue_context(
        tmp_path,
        dimension_id="quality-a",
        target_path=target_path,
    )

    with pytest.raises(ValueError, match="target_busy"):
        _issue_context(
            tmp_path,
            dimension_id="quality-b",
            target_path=target_path.parent / "." / target_path.name,
        )

    records = load_operation_records(tmp_path / "eval-operations.json")["operations"]
    assert list(records) == [first["operation_token"]]
    assert not list(tmp_path.rglob("*lease*"))

    cancel_operation_record(
        tmp_path / "eval-operations.json",
        first["operation_token"],
    )
    second = _issue_context(
        tmp_path,
        dimension_id="quality-b",
        target_path=target_path,
    )
    assert second["operation_token"] != first["operation_token"]


def test_conflict_is_checked_before_base_capture(tmp_path: Path):
    target_path = tmp_path / "target.md"
    target_path.write_text("target", encoding="utf-8")
    first = _issue_context(
        tmp_path,
        dimension_id="quality-a",
        target_path=target_path,
    )
    captured = False

    def _capture() -> dict:
        nonlocal captured
        captured = True
        raise AssertionError("base capture must not run while target is busy")

    with pytest.raises(ValueError, match="target_busy"):
        create_remediation_operation_record(
            tmp_path / "eval-operations.json",
            operation_token="other",
            round_token="round-1",
            dimension_id="quality-b",
            target_lease_key=target_path.resolve().as_posix(),
            capture_record=_capture,
        )

    assert captured is False
    assert get_operation_record(
        tmp_path / "eval-operations.json",
        first["operation_token"],
    )["phase"] == "context-open"
