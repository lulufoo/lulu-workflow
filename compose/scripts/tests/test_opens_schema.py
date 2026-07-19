#!/usr/bin/env python3
"""Tests for inductive-opens.json schema (K4 Phase 1a)."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from opens_schema import (  # noqa: E402
    blocking_open_items,
    load_opens,
    migrate_means,
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
        "source": {"trigger": "human", "means": "human_direct"},
        "kw": 1,
        "blocking": True,
        "problem": "gap",
        "detected_under": None,
    }
    base.update(overrides)
    return base


def test_mint_and_next_seq():
    assert mint_open_id(1) == "O-1"
    assert next_open_seq([]) == 1
    assert next_open_seq([_minimal_open()]) == 2


def test_validate_accepts_empty_and_minimal():
    assert validate_opens([]) == []
    assert validate_opens([_minimal_open()]) == []


def test_validate_rejects_non_contiguous_ids():
    errs = validate_opens(
        [
            _minimal_open(id="O-1"),
            _minimal_open(id="O-3", problem="second"),
        ]
    )
    assert any("O-2" in e for e in errs)


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


def test_validate_rejects_resolved_by_when_not_settled():
    errs = validate_opens(
        [_minimal_open(status="open", resolved_by=["F-1"])]
    )
    assert any("resolved_by" in e and "settled" in e for e in errs)


def test_validate_rejected_requires_reason():
    errs = validate_opens([_minimal_open(status="rejected")])
    assert any("reason" in e for e in errs)

    ok = validate_opens(
        [_minimal_open(status="rejected", reason="out of domain")]
    )
    assert ok == []


def test_validate_rejects_seed_trigger_on_open():
    """Seed bypasses opens; opens are discovered-only."""
    errs = validate_opens(
        [
            _minimal_open(
                source={"trigger": "seed", "means": "scope"},
            )
        ]
    )
    assert any("trigger" in e for e in errs)


def test_normalize_uppercases_detected_under():
    n = normalize_open(_minimal_open(detected_under="rn"))
    assert n["detected_under"] == "RN"


def test_save_load_round_trip(tmp_path: Path):
    opens = [
        _minimal_open(),
        _minimal_open(
            id="O-2",
            status="settled",
            blocking=False,
            problem="resolved gap",
            detected_under="FL",
            resolved_by=["F-7", "F-8"],
            leaning="prefer A",
        ),
    ]
    path = opens_path(tmp_path)
    save_opens(path, opens)
    loaded = load_opens(path)
    assert loaded[0]["id"] == "O-1"
    assert loaded[0]["detected_under"] is None
    assert loaded[1]["resolved_by"] == ["F-7", "F-8"]
    assert loaded[1]["detected_under"] == "FL"


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
                problem="done",
            )
        ),
        normalize_open(_minimal_open(id="O-3", blocking=False, problem="soft")),
    ]
    blocked = blocking_open_items(opens)
    assert [o["id"] for o in blocked] == ["O-1"]


def test_migrate_means_stock_map():
    assert migrate_means("human", "probe") == "human_probe"
    assert migrate_means("ai", "probe") == "ai_probe"
    assert migrate_means("human", "direct") == "human_direct"
    assert migrate_means("human", "view") == "human_view"
    assert migrate_means("ai", "intent_baseline") == "ai_intent_baseline"
    assert migrate_means("ai", "ai_scan") == "ai_scan"
    assert migrate_means("ai", "ai_scope_scan") == "ai_scope_scan"


def test_normalize_migrates_legacy_means():
    n = normalize_open(
        _minimal_open(source={"trigger": "ai", "means": "probe"})
    )
    assert n["source"] == {"trigger": "ai", "means": "ai_probe"}


def test_validate_rejects_prefix_trigger_mismatch():
    errs = validate_opens(
        [
            _minimal_open(
                source={"trigger": "human", "means": "ai_scope_scan"},
            )
        ]
    )
    assert any("prefix" in e and "trigger" in e for e in errs)


def test_save_load_rewrites_legacy_means(tmp_path: Path):
    path = opens_path(tmp_path)
    save_opens(
        path,
        [_minimal_open(source={"trigger": "human", "means": "direct"})],
    )
    loaded = load_opens(path)
    assert loaded[0]["source"]["means"] == "human_direct"
    # Disk rewritten with new means.
    assert '"human_direct"' in path.read_text(encoding="utf-8")


def test_ai_scope_scan_accepted():
    assert (
        validate_opens(
            [
                _minimal_open(
                    source={"trigger": "ai", "means": "ai_scope_scan"},
                    intent_ref="D-1",
                )
            ]
        )
        == []
    )
