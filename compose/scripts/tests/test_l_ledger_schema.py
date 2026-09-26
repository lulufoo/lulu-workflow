#!/usr/bin/env python3
"""Tests for l-ledger.json schema and global chain invariants."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

from compose_state_lock import canonical_digest
from l_ledger_schema import (
    active_slice_dir,
    build_ledger,
    ledger_fingerprint,
    load_l_ledger,
    reached_frontier,
    save_l_ledger,
    validate_l_ledger,
    working_slice_dir,
)


def _ok(order: list[str] | None = None) -> dict:
    return build_ledger(order or ["L1", "L2", "L3"])


def test_build_ledger_initial_shape() -> None:
    ledger = _ok()
    assert ledger["version"] == 1
    assert ledger["order"] == ["L1", "L2", "L3"]
    assert ledger["focus"] == "L1"
    assert ledger["by_id"]["L1"] == {"state": "Pending", "frozen": False}


def test_rejects_extra_top_level_key() -> None:
    ledger = _ok()
    ledger["ready"] = True
    assert any("unknown ledger keys" in err for err in validate_l_ledger(ledger))


def test_rejects_extra_cell_key() -> None:
    ledger = _ok()
    ledger["by_id"]["L1"]["title"] = "x"
    assert any("unknown keys" in err for err in validate_l_ledger(ledger))


def test_rejects_non_consecutive_order() -> None:
    raw = {
        "version": 1,
        "order": ["L1", "L3"],
        "focus": "L1",
        "by_id": {
            "L1": {"state": "Pending", "frozen": False},
            "L3": {"state": "Pending", "frozen": False},
        },
    }
    assert any("consecutive" in err for err in validate_l_ledger(raw))


def test_rejects_duplicate_order() -> None:
    raw = {
        "version": 1,
        "order": ["L1", "L1"],
        "focus": "L1",
        "by_id": {"L1": {"state": "Pending", "frozen": False}},
    }
    errors = validate_l_ledger(raw)
    assert any("duplicates" in err or "by_id keys" in err for err in errors)


def test_prefix_must_be_completed() -> None:
    ledger = _ok()
    ledger["focus"] = "L2"
    ledger["by_id"]["L1"]["state"] = "Writing"
    assert any("prefix of focus" in err for err in validate_l_ledger(ledger))


def test_normal_progress_shape() -> None:
    ledger = _ok()
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["focus"] = "L2"
    ledger["by_id"]["L2"]["state"] = "Writing"
    assert validate_l_ledger(ledger) == []


def test_first_backtrack_shape() -> None:
    ledger = _ok()
    ledger["focus"] = "L1"
    ledger["by_id"]["L1"] = {"state": "FreeEdit", "frozen": False}
    ledger["by_id"]["L2"] = {"state": "Completed", "frozen": True}
    ledger["by_id"]["L3"] = {"state": "Pending", "frozen": True}
    # L3 frozen while Pending is allowed; but i>r must be pending unfrozen.
    # r = max(focus=0, frozen {1,2}) = 2, so L3 is at r and may be frozen Pending.
    assert validate_l_ledger(ledger) == []
    assert reached_frontier(ledger) == 2


def test_partial_thaw_shape() -> None:
    ledger = _ok()
    ledger["by_id"]["L1"] = {"state": "Completed", "frozen": False}
    ledger["focus"] = "L2"
    ledger["by_id"]["L2"] = {"state": "Completed", "frozen": False}
    ledger["by_id"]["L3"] = {"state": "Pending", "frozen": True}
    assert validate_l_ledger(ledger) == []


def test_focus_must_not_be_frozen() -> None:
    ledger = _ok()
    ledger["by_id"]["L1"]["frozen"] = True
    assert any("focus must not be frozen" in err for err in validate_l_ledger(ledger))


def test_frozen_must_be_contiguous_after_focus() -> None:
    ledger = _ok()
    ledger["by_id"]["L3"]["frozen"] = True
    errors = validate_l_ledger(ledger)
    assert any("contiguous" in err for err in errors)


def test_save_load_roundtrip_and_fingerprint(tmp_path: Path) -> None:
    ledger = _ok()
    save_l_ledger(tmp_path, ledger)
    loaded = load_l_ledger(tmp_path)
    assert loaded == ledger
    assert ledger_fingerprint(loaded) == canonical_digest(loaded)


def test_save_rejects_invalid_without_writing(tmp_path: Path) -> None:
    ledger = _ok()
    ledger["ready"] = True
    with pytest.raises(ValueError):
        save_l_ledger(tmp_path, ledger)
    assert not (tmp_path / "l-ledger.json").exists()


def test_invalid_on_disk_does_not_load(tmp_path: Path) -> None:
    path = tmp_path / "l-ledger.json"
    path.write_text(json.dumps({"version": 1}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_l_ledger(tmp_path)


def test_working_slice_dir_remaps_revision_root(tmp_path: Path) -> None:
    save_l_ledger(tmp_path, build_ledger(["L1"]))
    assert working_slice_dir(tmp_path) == active_slice_dir(tmp_path)
    slice_dir = tmp_path / "L1"
    slice_dir.mkdir()
    assert working_slice_dir(slice_dir) == slice_dir.resolve()
