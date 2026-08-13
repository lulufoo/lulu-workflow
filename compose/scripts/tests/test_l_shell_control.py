#!/usr/bin/env python3
"""Tests for $L_SHELL command surface."""

from __future__ import annotations

import json

import bootstrap  # noqa: F401
import pytest

from l_ledger_schema import (
    build_ledger,
    ledger_fingerprint,
    load_l_ledger,
    save_l_ledger,
)
from l_shell_control import (
    cmd_advance,
    cmd_backtrack,
    cmd_status,
    cmd_unfreeze,
    cmd_view,
    derive_next_actions,
)


def _save(revision_dir, ledger):
    save_l_ledger(revision_dir, ledger)
    return ledger


def test_status_missing_ledger(tmp_path) -> None:
    payload = cmd_status(tmp_path, "Working")
    assert payload["ok"] is False
    assert payload["code"] == "unsupported_revision"


def test_status_working_pending(tmp_path) -> None:
    _save(tmp_path, build_ledger(["L1", "L2"]))
    payload = cmd_status(tmp_path, "Working")
    assert payload["ok"] is True
    assert payload["focus"] == "L1"
    assert payload["current"]["state"] == "Pending"
    assert payload["next"] == {"id": "L2", "state": "Pending", "frozen": False}
    assert "execute-current" in payload["next_actions"]
    assert "advance" not in payload["next_actions"]


def test_advance_requires_working(tmp_path) -> None:
    _save(tmp_path, build_ledger(["L1", "L2"]))
    payload = cmd_advance(tmp_path, "Split")
    assert payload["ok"] is False
    assert payload["code"] == "wrong_session_state"


def test_advance_completed_focus(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    _save(tmp_path, ledger)
    payload = cmd_advance(tmp_path, "Working")
    assert payload["ok"] is True
    assert payload["changed"] is True
    assert payload["focus"] == "L2"
    loaded = load_l_ledger(tmp_path)
    assert loaded["focus"] == "L2"


def test_advance_last_l_signals_ready(tmp_path) -> None:
    ledger = build_ledger(["L1"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    _save(tmp_path, ledger)
    payload = cmd_advance(tmp_path, "Working")
    assert payload["ok"] is True
    assert payload["changed"] is False
    assert payload["next_action"] == "ready-for-delivery"


def test_advance_frozen_successor_alignment(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2", "L3"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["frozen"] = True
    ledger["by_id"]["L3"]["frozen"] = True
    _save(tmp_path, ledger)
    payload = cmd_advance(tmp_path, "Working")
    assert payload["ok"] is False
    assert payload["code"] == "alignment_required"
    assert payload["successor"] == "L2"


def test_backtrack_requires_confirm(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["focus"] = "L2"
    ledger["by_id"]["L2"]["state"] = "Writing"
    _save(tmp_path, ledger)
    payload = cmd_backtrack(tmp_path, "Working", "L1", confirm=False)
    assert payload["code"] == "confirmation_required"


def test_backtrack_freezes_suffix(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2", "L3"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["focus"] = "L2"
    ledger["by_id"]["L2"]["state"] = "Writing"
    _save(tmp_path, ledger)
    payload = cmd_backtrack(tmp_path, "Working", "L1", confirm=True)
    assert payload["ok"] is True
    loaded = load_l_ledger(tmp_path)
    assert loaded["focus"] == "L1"
    assert loaded["by_id"]["L1"]["state"] == "FreeEdit"
    assert loaded["by_id"]["L2"]["frozen"] is True


def test_unfreeze_stale_fingerprint(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["frozen"] = True
    _save(tmp_path, ledger)
    payload = cmd_unfreeze(
        tmp_path,
        "Working",
        "0" * 64,
        confirm=True,
    )
    assert payload["ok"] is False
    assert payload["code"] == "stale_fingerprint"


def test_unfreeze_success(tmp_path) -> None:
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["frozen"] = True
    _save(tmp_path, ledger)
    digest = ledger_fingerprint(load_l_ledger(tmp_path))
    payload = cmd_unfreeze(tmp_path, "Working", digest, confirm=True)
    assert payload["ok"] is True
    loaded = load_l_ledger(tmp_path)
    assert loaded["focus"] == "L2"
    assert loaded["by_id"]["L2"]["frozen"] is False


def test_view_source_whitelist_excludes_facts_and_doc(tmp_path) -> None:
    _save(tmp_path, build_ledger(["L1"]))
    slice_dir = tmp_path / "L1"
    slice_dir.mkdir()
    (slice_dir / "scope-ref.json").write_text(
        '{"version": 1, "source_path": "/tmp/src.md"}\n',
        encoding="utf-8",
    )
    (slice_dir / "_facts.json").write_text(
        '[{"id":"F-1","text":"secret-fact"}]\n',
        encoding="utf-8",
    )
    (slice_dir / "design-doc.md").write_text("# secret-doc\n", encoding="utf-8")
    payload = cmd_view(tmp_path, "L1")
    assert payload["ok"] is True
    assert payload["source_path"] == "/tmp/src.md"
    dumped = json.dumps(payload)
    assert "secret-fact" not in dumped
    assert "secret-doc" not in dumped
    assert set(payload) <= {
        "ok",
        "command",
        "target",
        "state",
        "frozen",
        "slice_dir",
        "scope_ref_path",
        "source_path",
    }


def test_view_reads_scope_ref(tmp_path) -> None:
    _save(tmp_path, build_ledger(["L1"]))
    slice_dir = tmp_path / "L1"
    slice_dir.mkdir()
    (slice_dir / "scope-ref.json").write_text(
        '{"version": 1, "source_path": "/tmp/src.md"}\n',
        encoding="utf-8",
    )
    payload = cmd_view(tmp_path, "L1")
    assert payload["ok"] is True
    assert payload["source_path"] == "/tmp/src.md"


def test_derive_next_actions_ready(tmp_path) -> None:
    del tmp_path
    ledger = build_ledger(["L1"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    actions = derive_next_actions(ledger, "Working")
    assert "ready-for-delivery" in actions
    assert "reopen-current" in actions
