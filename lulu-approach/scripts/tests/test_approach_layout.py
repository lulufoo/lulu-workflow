#!/usr/bin/env python3
"""Tests for approach session layout."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_MODULE_PATH = _SCRIPTS / "approach_layout.py"
_spec = importlib.util.spec_from_file_location("approach_layout", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

ensure_approach_layout = _mod.ensure_approach_layout
decision_package_path = _mod.decision_package_path
is_rel_path_under_approach = _mod.is_rel_path_under_approach
resolve_under_approach = _mod.resolve_under_approach
relpath_from_approach = _mod.relpath_from_approach


def test_ensure_creates_approach_root(tmp_path: Path) -> None:
    root = tmp_path / "cycle" / "lulu-approach"
    got = ensure_approach_layout(root)
    assert got == root.resolve()
    assert root.is_dir()
    assert decision_package_path(root) == root.resolve() / "decision-package.json"
    assert not decision_package_path(root).exists()


def test_rel_path_rules_accept_under_root() -> None:
    assert is_rel_path_under_approach("decision-doc.md")
    assert is_rel_path_under_approach("decision-package.json")


def test_rel_path_rules_reject_escape_and_absolute() -> None:
    assert not is_rel_path_under_approach("../outside.json")
    assert not is_rel_path_under_approach("notes/../../etc/passwd")
    assert not is_rel_path_under_approach("/abs/path.json")
    assert not is_rel_path_under_approach("")


def test_resolve_under_approach_ok_and_reject(tmp_path: Path) -> None:
    root = ensure_approach_layout(tmp_path / "lulu-approach")
    doc = resolve_under_approach(root, "decision-doc.md")
    assert doc == root / "decision-doc.md"
    assert relpath_from_approach(root, doc) == "decision-doc.md"
    with pytest.raises(ValueError, match="relative under approach root"):
        resolve_under_approach(root, "../escape.json")
    with pytest.raises(ValueError, match="relative under approach root"):
        resolve_under_approach(root, "/tmp/outside.json")
    outside = tmp_path / "outside.json"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="outside approach root"):
        relpath_from_approach(root, outside)
