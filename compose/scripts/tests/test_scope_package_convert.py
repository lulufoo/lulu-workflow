"""Tests for scope-package → chain tree + source_path mirrors."""

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

from dependency_tree_schema import load_dependency_tree  # noqa: E402
from discussion_pointer_schema import load_discussion_pointer  # noqa: E402
from multi_slice_control import (  # noqa: E402
    cmd_lock_hard_mirror,
    cmd_lock_tree,
    cmd_write_intake,
)
from scope_package_convert import (  # noqa: E402
    ScopePackageConvertError,
    convert_scope_package,
    ensure_scope_package_convert,
)
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    chain_dependency_tree_from_scope_package,
    load_scope_ref_mirror,
    save_scope_package,
    stub_slice_rulers_from_scope_package,
)


def _pkg_single(source_path: str = "/tmp/D1/decision-fact.json") -> dict:
    return build_scope_package(
        slices=[{"id": "L1", "title": "Only", "source_path": source_path, "source_id": "main"}]
    )


def _pkg_multi(
    f1: str = "/tmp/D1/decision-fact.json",
    f2: str = "/tmp/D2/decision-fact.json",
) -> dict:
    return build_scope_package(
        slices=[
            {"id": "L1", "title": "Auth", "source_path": f1, "source_id": "D1"},
            {"id": "L2", "title": "Billing", "source_path": f2, "source_id": "D2"},
        ]
    )


def test_chain_from_slices_no_order_field() -> None:
    pkg = _pkg_multi()
    assert "order" not in pkg
    tree = chain_dependency_tree_from_scope_package(pkg)
    assert tree["order"] == ["L1", "L2"]
    assert tree["edges"] == [{"from": "L2", "to": "L1"}]
    assert stub_slice_rulers_from_scope_package(_pkg_single()) is None
    rulers = stub_slice_rulers_from_scope_package(pkg)
    assert rulers is not None
    assert rulers["cut_axis"] == "scope_package_slices"
    assert rulers["rulers"]["L1"]["job"] == "Auth"


def test_convert_single_l_chain_and_mirror(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    source_path = "/abs/path/main/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_single(source_path))

    result = convert_scope_package(rev, scope_package_path=pkg_path)
    assert result["ok"] is True
    assert result["node_ids"] == ["L1"]
    assert result["multi_l"] is False

    tree = load_dependency_tree(rev)
    assert tree["status"] == "locked"
    assert tree["order"] == ["L1"]
    assert tree["edges"] == []
    pointer = load_discussion_pointer(rev)
    assert pointer["focus"] == "L1"
    assert (rev / "L1").is_dir()
    mirror = load_scope_ref_mirror(rev, "L1")
    assert mirror["source_path"] == source_path
    # C3=B: mirror only — no source file materialization under Lx/
    assert not (rev / "L1" / "_facts").exists()


def test_convert_multi_l_chain_and_mirrors(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))

    result = convert_scope_package(rev, scope_package_path=pkg_path)
    assert result["node_ids"] == ["L1", "L2"]
    assert result["multi_l"] is True

    tree = load_dependency_tree(rev)
    assert tree["status"] == "locked"
    assert tree["order"] == ["L1", "L2"]
    assert tree["edges"] == [{"from": "L2", "to": "L1"}]
    assert load_scope_ref_mirror(rev, "L1")["source_path"] == f1
    assert load_scope_ref_mirror(rev, "L2")["source_path"] == f2
    assert (rev / "slice-rulers.json").is_file()


def test_convert_refuses_overwrite_when_locked(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg_path = save_scope_package(rev, _pkg_single())
    convert_scope_package(rev, scope_package_path=pkg_path)
    with pytest.raises(ScopePackageConvertError, match="already locked"):
        convert_scope_package(rev, scope_package_path=pkg_path)


def test_ensure_noop_when_already_converted(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg_path = save_scope_package(rev, _pkg_single("/x/fact.json"))
    convert_scope_package(rev, scope_package_path=pkg_path)
    second = ensure_scope_package_convert(rev, scope_package_path=pkg_path)
    assert second.get("noop") is True
    assert second["node_ids"] == ["L1"]


def test_reject_slice_mutation_commands(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    save_scope_package(rev, _pkg_single())
    assert cmd_write_intake(rev, intake_json='{"slots":{}}', intake_file=None) == 1
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(
                {
                    "version": 1,
                    "nodes": [{"id": "L1", "title": "X", "summary": "X"}],
                    "edges": [],
                    "order": ["L1"],
                }
            ),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 1
    )
    assert (
        cmd_lock_hard_mirror(
            rev,
            package_path=rev / "scope-package.json",
            confirm=True,
        )
        == 1
    )


def test_lock_hard_mirror_rejects_scope_package_path(tmp_path: Path) -> None:
    plan_rev = tmp_path / "plan-rev"
    plan_rev.mkdir()
    upstream = tmp_path / "design-rev"
    upstream.mkdir()
    pkg_path = save_scope_package(upstream, _pkg_single())
    assert cmd_lock_hard_mirror(plan_rev, package_path=pkg_path, confirm=True) == 1
