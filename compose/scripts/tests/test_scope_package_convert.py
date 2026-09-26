"""Tests for scope-package → ledger + source_path mirrors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from l_ledger_schema import load_l_ledger  # noqa: E402
from scope_package_convert import (  # noqa: E402
    ScopePackageConvertError,
    convert_scope_package,
    ensure_scope_package_convert,
)
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    load_scope_ref_mirror,
    save_scope_package,
)


def _pkg_single(source_path: str = "/tmp/D1/decision-doc.md") -> dict:
    return build_scope_package(
        slices=[{"id": "L1", "title": "Only", "source_path": source_path, "source_id": "main"}]
    )


def _pkg_multi(
    f1: str = "/tmp/D1/decision-doc.md",
    f2: str = "/tmp/D2/decision-doc.md",
) -> dict:
    return build_scope_package(
        slices=[
            {"id": "L1", "title": "Auth", "source_path": f1, "source_id": "D1"},
            {"id": "L2", "title": "Billing", "source_path": f2, "source_id": "D2"},
        ]
    )


def test_convert_does_not_write_dag_files(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg_path = save_scope_package(rev, _pkg_multi())
    convert_scope_package(rev, scope_package_path=pkg_path)
    for name in ("dependency-tree.json", "discussion-pointer.json", "slice-rulers.json"):
        assert not (rev / name).is_file()


def test_convert_single_l_chain_and_mirror(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    source_path = "/abs/path/main/decision-doc.md"
    pkg_path = save_scope_package(rev, _pkg_single(source_path))

    result = convert_scope_package(rev, scope_package_path=pkg_path)
    assert result["ok"] is True
    assert result["node_ids"] == ["L1"]
    assert result["multi_l"] is False

    tree = load_l_ledger(rev)
    assert tree["order"] == ["L1"]
    assert tree["focus"] == "L1"
    assert (rev / "L1").is_dir()
    mirror = load_scope_ref_mirror(rev, "L1")
    assert mirror["source_path"] == source_path
    # C3=B: mirror only — no source file materialization under Lx/
    assert not (rev / "L1" / "_facts").exists()


def test_convert_multi_l_chain_and_mirrors(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-doc.md"
    f2 = "/abs/D2/decision-doc.md"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))

    result = convert_scope_package(rev, scope_package_path=pkg_path)
    assert result["node_ids"] == ["L1", "L2"]
    assert result["multi_l"] is True

    ledger = load_l_ledger(rev)
    assert ledger["order"] == ["L1", "L2"]
    assert ledger["focus"] == "L1"
    assert load_scope_ref_mirror(rev, "L1")["source_path"] == f1
    assert load_scope_ref_mirror(rev, "L2")["source_path"] == f2
    assert not (rev / "slice-rulers.json").is_file()


def test_convert_refuses_overwrite_when_locked(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg_path = save_scope_package(rev, _pkg_single())
    convert_scope_package(rev, scope_package_path=pkg_path)
    with pytest.raises(ScopePackageConvertError, match="already published"):
        convert_scope_package(rev, scope_package_path=pkg_path)


def test_ensure_noop_when_already_converted(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg_path = save_scope_package(rev, _pkg_single("/x/fact.json"))
    convert_scope_package(rev, scope_package_path=pkg_path)
    second = ensure_scope_package_convert(rev, scope_package_path=pkg_path)
    assert second.get("noop") is True
    assert second["node_ids"] == ["L1"]
