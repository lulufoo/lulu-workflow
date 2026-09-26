#!/usr/bin/env python3
"""Tests for the persisted approach reopen transaction."""

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


def _reopen():
    path = _SCHEMA / "approach_reopen_schema.py"
    if not path.is_file():
        pytest.fail("approach_reopen_schema.py must define reopen transactions")
    return _load("approach_reopen_schema", path)


def test_shell_accepts_session_package_ready_and_reopen() -> None:
    for macro_state in ("Session", "PackageReady", "Reopen"):
        shell = _shell.build_shell(macro_state=macro_state)
        assert _shell.validate_shell(shell) == []


def test_reopen_transaction_round_trip(tmp_path: Path) -> None:
    reopen = _reopen()
    transaction = reopen.build_reopen(
        transaction_id="reopen-001",
        state="preparing",
        previous={
            "macro_state": "Session",
            "active_session": ".",
        },
    )

    path = reopen.save_reopen(tmp_path, transaction)

    assert path == tmp_path / "reopen.json"
    loaded = reopen.load_reopen(tmp_path)
    assert loaded["state"] == "preparing"
    assert loaded["previous"]["macro_state"] == "Session"
    assert loaded["previous"]["active_session"] == "."
