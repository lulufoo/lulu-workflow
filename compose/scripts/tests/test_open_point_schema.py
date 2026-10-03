#!/usr/bin/env python3
"""Tests for Open-point state, batch, receipt, and transaction schemas."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "topic", "open-point", "recompose"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))

from compose_state_lock import canonical_digest  # noqa: E402
from open_point_batch_schema import (  # noqa: E402
    empty_open_point_batches,
    normalize_open_point_batches,
    validate_open_point_batches,
)
from open_point_detect_receipt_schema import (  # noqa: E402
    empty_open_point_receipts,
    normalize_open_point_receipts,
    parse_detect_verdicts,
    validate_detect_verdicts,
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
        "raw_candidate_count": 0,
        "lens_measurements": [
            {"lens": "I", "gap_kw": None},
            {"lens": "FL", "gap_kw": None},
        ],
    }
    base.update(overrides)
    return base


def _verdict(lens="I", gap_kw=None, candidates=None, **extra):
    item = {"lens": lens, "gap_kw": gap_kw, "candidates": list(candidates or [])}
    item.update(extra)
    return item


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


def test_receipt_slim_shape_valid():
    assert validate_open_point_receipts(_receipts(_receipt())) == []
    payload = _receipts(
        _receipt(
            raw_candidate_count=3,
            lens_measurements=[
                {"lens": "I", "gap_kw": 1},
                {"lens": "FL", "gap_kw": None},
            ],
        )
    )
    assert validate_open_point_receipts(payload) == []


def test_receipt_accepts_and_drops_legacy_fields():
    legacy = _receipt(
        checked_lenses=["I", "FL"],
        raw_candidate_digest=_DIGEST,
        final_open_ids=[],
        zero_result=True,
        lens_measurements=[
            {"lens": "I", "start_kw": 0, "gap_kw": None},
            {"lens": "FL", "start_kw": 0, "gap_kw": None},
        ],
    )
    assert validate_open_point_receipts(_receipts(legacy)) == []
    normalized = normalize_open_point_receipts(_receipts(legacy))
    assert normalized["receipts"][0] == _receipt()


def test_receipt_requires_lens_measurements():
    raw = _receipt()
    del raw["lens_measurements"]
    errs = validate_open_point_receipts(_receipts(raw))
    assert any("lens_measurements" in e for e in errs)
    errs = validate_open_point_receipts(
        _receipts(_receipt(lens_measurements=[{"lens": "I", "gap_kw": 9}]))
    )
    assert any("gap_kw" in e for e in errs)


def test_verdicts_require_registry_coverage():
    verdicts = [_verdict("I"), _verdict("FL")]
    assert validate_detect_verdicts(verdicts, registry_lenses=["I", "FL"]) == []
    errs = validate_detect_verdicts([_verdict("I")], registry_lenses=["I", "FL"])
    assert any("missing" in e for e in errs)
    errs = validate_detect_verdicts(
        [_verdict("I"), _verdict("FL"), _verdict("XX")],
        registry_lenses=["I", "FL"],
    )
    assert any("unknown" in e for e in errs)


def test_verdicts_gap_and_candidates_move_together():
    errs = validate_detect_verdicts(
        [_verdict("I", gap_kw=1, candidates=[])], registry_lenses=["I"]
    )
    assert any("candidates" in e for e in errs)
    errs = validate_detect_verdicts(
        [_verdict("I", gap_kw=None, candidates=[{"question": "q"}])],
        registry_lenses=["I"],
    )
    assert any("candidates" in e for e in errs)


def test_verdict_candidate_kw_must_match_gap_when_present():
    ok = [_verdict("I", gap_kw=2, candidates=[{"question": "a", "kw": 3}, {"question": "b", "kw": 2}])]
    assert validate_detect_verdicts(ok, registry_lenses=["I"]) == []
    wrong = [_verdict("I", gap_kw=3, candidates=[{"question": "a", "kw": 3}, {"question": "b", "kw": 2}])]
    errs = validate_detect_verdicts(wrong, registry_lenses=["I"])
    assert any("coarsest candidate kw 2" in e for e in errs)
    errs = validate_detect_verdicts(
        [_verdict("I", gap_kw=1, candidates=[{"question": "a", "kw": 2}])],
        registry_lenses=["I"],
    )
    assert any("coarsest candidate kw 2" in e for e in errs)


def test_verdict_candidate_without_kw_passes_and_bad_kw_fails():
    mixed = [_verdict("I", gap_kw=1, candidates=[{"question": "a"}, {"question": "b", "kw": 3}])]
    assert validate_detect_verdicts(mixed, registry_lenses=["I"]) == []
    bad = [_verdict("I", gap_kw=1, candidates=[{"question": "a", "kw": 9}])]
    errs = validate_detect_verdicts(bad, registry_lenses=["I"])
    assert any("kw must be an int" in e for e in errs)


def test_parse_detect_verdicts_normalizes():
    parsed = parse_detect_verdicts(
        [
            _verdict("i", gap_kw=1, candidates=[{"question": "q"}]),
            _verdict("FL"),
        ],
        registry_lenses=["I", "FL"],
    )
    assert parsed[0]["lens"] == "I"
    assert parsed[0]["gap_kw"] == 1
    assert parsed[0]["candidates"] == [{"question": "q"}]
    assert parsed[1] == {"lens": "FL", "gap_kw": None, "candidates": []}


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
