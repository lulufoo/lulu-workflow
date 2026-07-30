#!/usr/bin/env python3
"""Tests for approach node-binding.json schema."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"
_DECISION_SCRIPTS = _SCRIPTS.parents[1] / "decision" / "scripts"
for _p in (_SCHEMA, _DECISION_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_nb = _load("approach_node_binding_schema", _SCHEMA / "approach_node_binding_schema.py")


def test_new_binding_id_unique() -> None:
    a = _nb.new_binding_id()
    b = _nb.new_binding_id()
    assert a != b
    assert a.startswith("bind-")


def test_save_load_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    root.mkdir()
    payload = _nb.build_node_binding(
        binding_id="bind-test1",
        state="preparing",
        previous={"focus": "D2", "active_session": "D2"},
        target={"node_id": "D1", "session_dir": "D1"},
        context_snapshot={"path": "bindings/bind-test1/resolved-context.json", "sha256": "abc"},
        frozen_nodes=["D1", "D2"],
        operation="reopen",
        permit_path="bindings/bind-test1/permit.json",
        permit_state="issued",
    )
    path = _nb.save_node_binding(root, payload)
    assert path.is_file()
    loaded = _nb.load_node_binding(root)
    assert loaded["binding_id"] == "bind-test1"
    assert loaded["state"] == "preparing"
    assert loaded["frozen_nodes"] == ["D1", "D2"]
    assert loaded["permit_state"] == "issued"


def test_validate_rejects_bad_state() -> None:
    with pytest.raises(ValueError, match="state"):
        _nb.validate_node_binding(
            {
                "version": "1",
                "binding_id": "bind-x",
                "state": "nope",
                "previous": {"focus": None, "active_session": None},
                "target": {"node_id": "D1", "session_dir": "D1"},
                "context_snapshot": {"path": "", "sha256": ""},
                "frozen_nodes": [],
                "operation": "enter",
                "permit_path": None,
                "permit_state": "none",
            }
        )


def test_atomic_write_no_tmp_left(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    root.mkdir()
    payload = _nb.build_node_binding(
        binding_id="bind-a",
        state="bound",
        previous={"focus": "D1", "active_session": "D1"},
        target={"node_id": "D1", "session_dir": "D1"},
        operation="enter",
    )
    _nb.save_node_binding(root, payload)
    leftovers = list(root.glob("*.tmp"))
    assert leftovers == []
    data = json.loads((_nb.node_binding_path(root)).read_text(encoding="utf-8"))
    assert data["state"] == "bound"


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _nb.load_node_binding(tmp_path / "missing")
