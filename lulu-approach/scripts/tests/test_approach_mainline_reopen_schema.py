#!/usr/bin/env python3
"""Tests for the persisted Main/Split reopen transaction."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_shell = _load("approach_shell_schema", _SCHEMA / "approach_shell_schema.py")


def _mainline():
    path = _SCHEMA / "approach_mainline_reopen_schema.py"
    if not path.is_file():
        pytest.fail("approach_mainline_reopen_schema.py must define reopen transactions")
    return _load("approach_mainline_reopen_schema", path)


def test_reopen_macro_states_require_main_focus() -> None:
    for macro_state in ("MainReopen", "SplitReopen"):
        shell = _shell.build_shell(macro_state=macro_state, focus="main")
        assert _shell.validate_shell(shell) == []

        shell["focus"] = "D1"
        assert f"{macro_state} focus must be main" in _shell.validate_shell(shell)


def test_mainline_transaction_round_trip_preserves_main_target(tmp_path: Path) -> None:
    mainline = _mainline()
    transaction = mainline.build_mainline_reopen(
        transaction_id="mlr-001",
        target={"kind": "main", "node_id": "main"},
        state="preparing",
        previous={
            "macro_state": "Working",
            "focus": "D2",
            "active_session": "D2",
        },
        frozen={"split": True, "nodes": ["D1", "D2"]},
    )

    path = mainline.save_mainline_reopen(tmp_path, transaction)

    assert path == tmp_path / "mainline-reopen.json"
    loaded = mainline.load_mainline_reopen(tmp_path)
    assert loaded["target"] == {"kind": "main", "node_id": "main"}
    assert loaded["frozen"] == {"split": True, "nodes": ["D1", "D2"]}
