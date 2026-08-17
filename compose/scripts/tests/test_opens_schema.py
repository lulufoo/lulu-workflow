#!/usr/bin/env python3
"""Tests for rewritten inductive-opens.json schema (open-point contract)."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from compose_state_lock import canonical_digest  # noqa: E402
from opens_schema import (  # noqa: E402
    blocking_open_items,
    load_opens,
    mint_open_id,
    next_open_seq,
    normalize_open,
    opens_path,
    save_opens,
    validate_opens,
)


def _minimal_open(**overrides):
    base = {
        "id": "O-1",
        "status": "open",
        "source": {"actor": "human", "means": "direct"},
        "question": "What is the failure mode?",
        "basis": "Collision between intent and current facts",
        "blocking": True,
        "lens": "I",
    }
    base.update(overrides)
    return base


def test_mint_and_next_seq_allows_gaps():
    assert mint_open_id(1) == "O-1"
    assert next_open_seq([]) == 1
    assert next_open_seq([_minimal_open()]) == 2
    assert next_open_seq([_minimal_open(), _minimal_open(id="O-3")]) == 4


def test_validate_accepts_empty_and_gap_ids():
    assert validate_opens([]) == []
    assert validate_opens([_minimal_open()]) == []
    assert (
        validate_opens(
            [
                _minimal_open(id="O-1"),
                _minimal_open(id="O-3", question="second"),
            ]
        )
        == []
    )


def test_validate_rejects_missing_required_fields():
    for field in ("id", "status", "source", "question", "basis", "blocking", "lens"):
        raw = _minimal_open()
        del raw[field]
        errs = validate_opens([raw])
        assert any(field in e for e in errs), field


def test_validate_rejects_old_fields():
    for field, value in (
        ("problem", "gap"),
        ("kw", 1),
        ("trigger", "human"),
        ("facet_id", "runtime_degradation"),
    ):
        errs = validate_opens([_minimal_open(**{field: value})])
        assert any("unexpected" in e and field in e for e in errs), field


def test_validate_accepts_scan_intent_probe_means():
    for means in ("scan", "intent", "probe"):
        assert (
            validate_opens(
                [_minimal_open(source={"actor": "ai", "means": means})]
            )
            == []
        )


def test_validate_rejects_invalid_actor_and_means():
    errs = validate_opens(
        [_minimal_open(source={"actor": "seed", "means": "direct"})]
    )
    assert any("actor" in e for e in errs)

    errs = validate_opens(
        [_minimal_open(source={"actor": "human", "means": "human_direct"})]
    )
    assert any("means" in e for e in errs)


def test_validate_rejects_unexpected_source_fields():
    errs = validate_opens(
        [
            _minimal_open(
                source={"actor": "human", "means": "direct", "trigger": "human"}
            )
        ]
    )
    assert any("source" in e and "unexpected" in e for e in errs)


def test_validate_settled_requires_resolved_by():
    errs = validate_opens([_minimal_open(status="settled")])
    assert any("resolved_by" in e for e in errs)

    ok = validate_opens(
        [_minimal_open(status="settled", resolved_by=["F-1", "F-2"])]
    )
    assert ok == []


def test_validate_deferred_requires_note():
    errs = validate_opens([_minimal_open(status="deferred")])
    assert any("note" in e for e in errs)

    ok = validate_opens(
        [_minimal_open(status="deferred", note="park for later")]
    )
    assert ok == []


def test_validate_rejected_requires_reason():
    errs = validate_opens([_minimal_open(status="rejected")])
    assert any("reason" in e for e in errs)

    ok = validate_opens(
        [_minimal_open(status="rejected", reason="out of domain")]
    )
    assert ok == []


def test_validate_rejects_resolved_by_when_not_settled():
    errs = validate_opens([_minimal_open(status="open", resolved_by=["F-1"])])
    assert any("resolved_by" in e for e in errs)


def test_save_load_round_trip(tmp_path: Path):
    opens = [
        _minimal_open(),
        _minimal_open(
            id="O-3",
            status="settled",
            blocking=False,
            question="resolved gap",
            resolved_by=["F-7", "F-8"],
            code_refs=["src/a.py:10"],
        ),
    ]
    path = opens_path(tmp_path)
    save_opens(path, opens)
    loaded = load_opens(path)
    assert [item["id"] for item in loaded] == ["O-1", "O-3"]
    assert loaded[1]["resolved_by"] == ["F-7", "F-8"]
    assert loaded[1]["code_refs"] == ["src/a.py:10"]
    assert "problem" not in loaded[0]
    assert "kw" not in loaded[0]


def test_load_missing_file_returns_empty(tmp_path: Path):
    assert load_opens(opens_path(tmp_path)) == []


def test_blocking_open_items_filters():
    opens = [
        normalize_open(_minimal_open(id="O-1", blocking=True)),
        normalize_open(
            _minimal_open(
                id="O-2",
                status="settled",
                blocking=True,
                resolved_by=["F-1"],
                question="done",
            )
        ),
        normalize_open(_minimal_open(id="O-3", blocking=False, question="soft")),
    ]
    blocked = blocking_open_items(opens)
    assert [item["id"] for item in blocked] == ["O-1"]


def test_no_migrate_helpers_exported():
    import opens_schema

    assert not hasattr(opens_schema, "migrate_means")
    assert not hasattr(opens_schema, "migrate_open_source")
    assert not hasattr(opens_schema, "TRIGGERS")


def test_versioned_array_digest_changes_with_payload():
    first = canonical_digest([normalize_open(_minimal_open())])
    second = canonical_digest(
        [normalize_open(_minimal_open(question="changed"))]
    )
    assert first != second
