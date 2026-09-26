#!/usr/bin/env python3
"""Tests for approach nested session layout (archive-1.0 P2.dirs)."""

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
main_session_dir = _mod.main_session_dir
dx_session_dir = _mod.dx_session_dir
approach_root_from_session_dir = _mod.approach_root_from_session_dir
decision_package_path = _mod.decision_package_path
is_rel_path_under_approach = _mod.is_rel_path_under_approach
resolve_under_approach = _mod.resolve_under_approach
relpath_from_approach = _mod.relpath_from_approach


def test_ensure_no_split_creates_main_only(tmp_path: Path) -> None:
    root = tmp_path / "cycle" / "lulu-approach"
    got = ensure_approach_layout(root)
    assert got == root.resolve()
    assert main_session_dir(root).is_dir()
    assert not (root / "D1").exists()
    assert not (root / "gate-state.json").exists()
    assert decision_package_path(root) == root.resolve() / "decision-package.json"
    assert not decision_package_path(root).exists()


def test_ensure_with_dx_creates_isolated_session_dirs(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    ensure_approach_layout(root, dx_ids=["D1", "D2"])
    main = main_session_dir(root)
    d1 = dx_session_dir(root, "D1")
    d2 = dx_session_dir(root, "D2")
    assert main.is_dir()
    assert d1.is_dir()
    assert d2.is_dir()
    assert main != d1
    assert d1.parent == root.resolve()
    assert d2.parent == root.resolve()
    # session isolation: artifacts under Dx do not land on outer root
    (d1 / "gate-state.json").write_text("{}", encoding="utf-8")
    assert not (root / "gate-state.json").exists()
    assert (d1 / "gate-state.json").is_file()


def test_approach_root_from_main_and_dx(tmp_path: Path) -> None:
    root = ensure_approach_layout(tmp_path / "lulu-approach", dx_ids=["D1"])
    assert approach_root_from_session_dir(main_session_dir(root)) == root
    assert approach_root_from_session_dir(dx_session_dir(root, "D1")) == root


def test_approach_root_rejects_non_session_dir(tmp_path: Path) -> None:
    root = ensure_approach_layout(tmp_path / "lulu-approach")
    with pytest.raises(ValueError, match="main/ or Dx/"):
        approach_root_from_session_dir(root)


def test_dx_session_dir_rejects_bad_id(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    with pytest.raises(ValueError, match="D<number>"):
        dx_session_dir(root, "main")
    with pytest.raises(ValueError, match="D<number>"):
        dx_session_dir(root, "L1")


def test_rel_path_rules_accept_under_root() -> None:
    assert is_rel_path_under_approach("main/decision-doc.md")
    assert is_rel_path_under_approach("D1/decision-doc.md")
    assert is_rel_path_under_approach("decision-package.json")


def test_rel_path_rules_reject_escape_and_absolute() -> None:
    assert not is_rel_path_under_approach("../outside.json")
    assert not is_rel_path_under_approach("main/../../etc/passwd")
    assert not is_rel_path_under_approach("/abs/path.json")
    assert not is_rel_path_under_approach("")


def test_resolve_under_approach_ok_and_reject(tmp_path: Path) -> None:
    root = ensure_approach_layout(tmp_path / "lulu-approach", dx_ids=["D1"])
    doc = resolve_under_approach(root, "main/decision-doc.md")
    assert doc == root / "main" / "decision-doc.md"
    assert relpath_from_approach(root, doc) == "main/decision-doc.md"
    with pytest.raises(ValueError, match="relative under approach root"):
        resolve_under_approach(root, "../escape.json")
    with pytest.raises(ValueError, match="relative under approach root"):
        resolve_under_approach(root, "/tmp/outside.json")
    outside = tmp_path / "outside.json"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="outside approach root"):
        relpath_from_approach(root, outside)
