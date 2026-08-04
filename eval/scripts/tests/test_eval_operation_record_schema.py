#!/usr/bin/env python3
"""Tests for eval/scripts/eval_operation_record_schema.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_operation_record_schema import (  # noqa: E402
    OPERATION_RECORDS_VERSION,
    close_operation,
    empty_operation_records,
    save_operation_records,
    validate_operation_record,
)

_DIGEST = "a" * 64


def _human_resolution_record(*, status: str = "open") -> dict:
    return {
        "round_token": "round-1",
        "dimension_token": "dimension-1",
        "dimension_id": "e2",
        "operation_kind": "human-resolution",
        "staging_scope": "scope-1",
        "snapshot_path": "/tmp/snapshot.md",
        "target_digest": _DIGEST,
        "resolved_method": {},
        "resolved_sots": [],
        "evidence_snapshots": {},
        "allowed_submission": "resolution",
        "status": status,
        "lease_id": "lease-1",
    }


class TestOperationRecordSchema:
    def test_empty_records_uses_current_version(self):
        assert OPERATION_RECORDS_VERSION == "2"
        assert empty_operation_records()["version"] == "2"

    def test_human_resolution_requires_lease(self):
        record = _human_resolution_record()
        del record["lease_id"]
        errors = validate_operation_record(record)
        assert "remediation operation requires a non-empty lease_id" in errors

    def test_sot_remediation_operation_kind_is_rejected(self):
        record = _human_resolution_record()
        record["operation_kind"] = "sot-remediation"
        errors = validate_operation_record(record)
        assert any("invalid operation_kind" in error for error in errors)

    def test_closed_human_resolution_validates_resolution_records(self):
        record = _human_resolution_record(status="closed")
        record.update({
            "submission_digest": _DIGEST,
            "review_path": "/tmp/review.md",
            "review_digest": _DIGEST,
            "resolution_records": [{"issue_id": "e2-1", "resolution": "choose A"}],
        })
        assert validate_operation_record(record) == []

        record["resolution_records"] = ["not an object"]
        errors = validate_operation_record(record)
        assert "resolution_records must be an array of objects on a closed human-resolution operation" in errors

    def test_close_human_resolution_preserves_resolution_records(self, tmp_path: Path):
        path = tmp_path / "operation-records.json"
        record = _human_resolution_record()
        save_operation_records(
            path,
            {"version": OPERATION_RECORDS_VERSION, "operations": {"dimension-1": record}},
        )
        closed = close_operation(
            path,
            dimension_token="dimension-1",
            submission_digest=_DIGEST,
            review_path=tmp_path / "review.md",
            review_digest=_DIGEST,
            resolution_records=[{"issue_id": "e2-1", "resolution": "choose A"}],
        )
        assert closed["resolution_records"] == [
            {"issue_id": "e2-1", "resolution": "choose A"},
        ]
