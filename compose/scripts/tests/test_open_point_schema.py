#!/usr/bin/env python3
"""Tests for Open-point state, batch, receipt, and transaction schemas."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SCHEMA_DIR = _INDUCTIVE_DIR / "schema"
sys.path.insert(0, str(_INDUCTIVE_DIR))
sys.path.insert(0, str(_SCHEMA_DIR))

from compose_state_lock import canonical_digest  # noqa: E402
from open_point_batch_schema import (  # noqa: E402
    empty_open_point_batches,
    normalize_open_point_batches,
    validate_open_point_batches,
)
from open_point_detect_receipt_schema import (  # noqa: E402
    empty_open_point_receipts,
    normalize_open_point_receipts,
    validate_open_point_receipts,
)
from open_point_state_schema import (  # noqa: E402
    empty_open_point_state,
    load_open_point_state,
    normalize_open_point_state,
    open_point_state_path,
    validate_open_point_state,
)
from open_point_transaction_schema import (  # noqa: E402
    normalize_open_point_txn,
    validate_open_point_txn,
)

_DIGEST = canonical_digest([])


def _idle_state(**overrides):
    base = empty_open_point_state()
    base.update(overrides)
    return base


def _processing_state(**overrides):
    base = {
        "version": 1,
        "phase": "processing",
        "active_batch_id": "B-1",
        "active_open_id": "O-1",
    }
    base.update(overrides)
    return base


def _batches(*items):
    return {"version": 1, "batches": list(items)}


def _batch(**overrides):
    base = {
        "id": "B-1",
        "status": "active",
        "detect_receipt_id": "R-1",
        "open_ids": ["O-1"],
    }
    base.update(overrides)
    return base


def _receipts(*items):
    return {"version": 1, "receipts": list(items)}


def _receipt(**overrides):
    base = {
        "id": "R-1",
        "checked_lenses": ["I", "FL"],
        "facts_digest": _DIGEST,
        "lens_digest": _DIGEST,
        "opens_digest": _DIGEST,
        "frontier_digest": _DIGEST,
        "raw_candidate_count": 0,
        "raw_candidate_digest": _DIGEST,
        "final_open_ids": [],
        "zero_result": True,
    }
    base.update(overrides)
    return base


def _txn(**overrides):
    base = {
        "version": 1,
        "operation": "add-opens",
        "targets": {
            "inductive-opens.json": {
                "existed": False,
                "before": None,
                "after_digest": _DIGEST,
            }
        },
    }
    base.update(overrides)
    return base


def test_state_idle_requires_null_actives():
    assert validate_open_point_state(_idle_state()) == []
    errs = validate_open_point_state(_idle_state(active_batch_id="B-1"))
    assert any("idle" in e for e in errs)
    errs = validate_open_point_state(_idle_state(active_open_id="O-1"))
    assert any("idle" in e for e in errs)


def test_state_processing_requires_active_batch():
    assert validate_open_point_state(_processing_state()) == []
    errs = validate_open_point_state(_processing_state(active_batch_id=None))
    assert any("processing" in e for e in errs)


def test_state_missing_file_is_empty_idle(tmp_path: Path):
    loaded = load_open_point_state(open_point_state_path(tmp_path))
    assert loaded == empty_open_point_state()
    assert loaded["phase"] == "idle"
    assert loaded["active_batch_id"] is None
    assert loaded["active_open_id"] is None


def test_state_version_change_changes_digest():
    first = canonical_digest(normalize_open_point_state(_idle_state()))
    second = canonical_digest(
        {**normalize_open_point_state(_idle_state()), "version": 2}
    )
    assert first != second


def test_batches_at_most_one_active():
    assert validate_open_point_batches(_batches(_batch())) == []
    errs = validate_open_point_batches(
        _batches(_batch(id="B-1"), _batch(id="B-2", open_ids=["O-2"]))
    )
    assert any("active" in e for e in errs)


def test_batches_accept_gap_ids_and_null_receipt():
    payload = _batches(
        _batch(id="B-1", status="completed", detect_receipt_id=None),
        _batch(id="B-3", open_ids=["O-2", "O-4"]),
    )
    assert validate_open_point_batches(payload) == []


def test_batches_reject_duplicate_open_ids_in_batch():
    errs = validate_open_point_batches(
        _batches(_batch(open_ids=["O-1", "O-1"]))
    )
    assert any("open_ids" in e for e in errs)


def test_empty_batches_shape():
    empty = empty_open_point_batches()
    assert empty == {"version": 1, "batches": []}
    assert validate_open_point_batches(empty) == []


def test_receipt_zero_result_only_when_raw_count_zero():
    assert validate_open_point_receipts(_receipts(_receipt())) == []
    errs = validate_open_point_receipts(
        _receipts(_receipt(raw_candidate_count=2, zero_result=True))
    )
    assert any("zero_result" in e for e in errs)
    errs = validate_open_point_receipts(
        _receipts(_receipt(raw_candidate_count=0, zero_result=False))
    )
    assert any("zero_result" in e for e in errs)


def test_receipt_accepts_non_zero_with_empty_final_ids():
    payload = _receipts(
        _receipt(
            raw_candidate_count=3,
            zero_result=False,
            final_open_ids=[],
        )
    )
    assert validate_open_point_receipts(payload) == []


def test_receipt_requires_checked_lenses():
    raw = _receipt()
    del raw["checked_lenses"]
    errs = validate_open_point_receipts(_receipts(raw))
    assert any("checked_lenses" in e for e in errs)
    errs = validate_open_point_receipts(
        _receipts(_receipt(checked_lenses=[]))
    )
    assert any("checked_lenses" in e for e in errs)


def test_empty_receipts_shape():
    empty = empty_open_point_receipts()
    assert empty == {"version": 1, "receipts": []}
    assert validate_open_point_receipts(empty) == []


def test_txn_validates_envelope():
    assert validate_open_point_txn(_txn()) == []
    errs = validate_open_point_txn({"version": 1, "operation": "add-opens"})
    assert any("targets" in e for e in errs)
    errs = validate_open_point_txn(_txn(legacy=True))
    assert any("unexpected" in e for e in errs)


def test_txn_target_requires_existed_before_after_digest():
    errs = validate_open_point_txn(
        _txn(
            targets={
                "inductive-opens.json": {
                    "existed": False,
                    "after_digest": _DIGEST,
                }
            }
        )
    )
    assert any("before" in e for e in errs)


def test_normalize_preserves_integer_version():
    assert normalize_open_point_state(_idle_state())["version"] == 1
    assert normalize_open_point_batches(_batches())["version"] == 1
    assert normalize_open_point_receipts(_receipts())["version"] == 1
    assert normalize_open_point_txn(_txn())["version"] == 1
