#!/usr/bin/env python3
"""Tests for approach Split structural cut (archive-1.0 P2.split)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCHEMA))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_layout = _load("approach_layout", _SCRIPTS / "approach_layout.py")
_shell_schema = _load("approach_shell_schema", _SCHEMA / "approach_shell_schema.py")
_pkg = _load("decision_package_schema", _SCHEMA / "decision_package_schema.py")
_shell = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")
_split = _load("approach_split_control", _SCRIPTS / "approach_split_control.py")

init_shell = _shell.init_shell
enter_split = _shell.enter_split
enter_working = _shell.enter_working
set_focus = _shell.set_focus
mark_node_delivered = _shell.mark_node_delivered
main_session_dir = _layout.main_session_dir
write_early_package = _split.write_early_package
write_intake = _split.write_intake
complete_intake = _split.complete_intake
deliver_split = _split.deliver_split
ensure_dx_on_focus = _split.ensure_dx_on_focus
build_tree = _split.build_tree
build_decision_rulers = _split.build_decision_rulers
empty_intake = _split.empty_intake
load_decision_package = _pkg.load_decision_package
validate_decision_package = _pkg.validate_decision_package


def _write_delivered(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: Delivered\nupdated_at: 2026-07-29T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _filled_intake() -> dict:
    data = empty_intake()
    data["slots"] = {
        "split_goal": "cut by ownership seams",
        "candidate_structure_faces": "Host; Binding Contract",
        "deps_order": "D1 before D2",
        "slice_autonomy": "each Dx is an executable sub-tech plan",
        "non_goals": "no cross-compose shared kernel",
        "split_risks": "topo chain friction downstream",
    }
    data["recommend_split"] = True
    return data


def _sample_tree() -> dict:
    return build_tree(
        nodes=[
            {"id": "D1", "title": "Host + Contract", "summary": "base seam"},
            {"id": "D2", "title": "Todos + entry", "summary": "depends on D1"},
        ],
        edges=[{"from": "D2", "to": "D1"}],
        order=["D1", "D2"],
        status="draft",
    )


def _sample_rulers() -> dict:
    return build_decision_rulers(
        cut_axis="domain_seam",
        rulers={
            "D1": {
                "id": "D1",
                "job": "define Host + Binding Contract",
                "boundary": "no Todos UI / parity",
                "deps_summary": "none (root)",
            },
            "D2": {
                "id": "D2",
                "job": "Todos page entry + parity",
                "boundary": "consumes contract; no Host rewrite",
                "deps_summary": "depends on D1",
            },
        },
        status="draft",
    )


def _enter_split_ready(root: Path) -> None:
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)


def test_empty_slices_allowed_early(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    pkg = write_early_package(root)
    assert pkg["slices"] == []
    assert validate_decision_package(pkg) == []
    loaded = load_decision_package(root / "decision-package.json")
    assert loaded["slices"] == []
    assert not (root / "D1").exists()


def test_split_delivered_writes_ordered_slices(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    _enter_split_ready(root)
    write_early_package(root)
    write_intake(root, _filled_intake())
    complete_intake(root, confirm=True)

    result = deliver_split(
        root, tree=_sample_tree(), rulers=_sample_rulers(), confirm=True
    )
    assert result["split_delivered"] is True
    assert [s["id"] for s in result["slices"]] == ["D1", "D2"]
    assert result["slices"][0]["decision_fact_path"] == "D1/decision-fact.json"
    assert result["slices"][0]["decision_doc_path"] == "D1/decision-doc.md"
    assert result["slices"][1]["decision_fact_path"] == "D2/decision-fact.json"

    package = load_decision_package(root / "decision-package.json")
    assert [s["id"] for s in package["slices"]] == ["D1", "D2"]
    assert package["status"] == "split_delivered"
    # conventional paths written; files / Dx dirs need not exist yet (S4=A)
    assert not (root / "D1").exists()
    assert not (root / "D2").exists()
    assert not (root / "D1" / "decision-fact.json").exists()


def test_dx_created_only_on_focus(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    _enter_split_ready(root)
    deliver_split(
        root, tree=_sample_tree(), rulers=_sample_rulers(), confirm=True
    )
    assert not (root / "D1").exists()
    assert not (root / "D2").exists()

    shell = enter_working(root, ["D1", "D2"], focus="D1")
    assert shell["focus"] == "D1"
    assert (root / "D1").is_dir()
    assert not (root / "D2").exists()

    mark_node_delivered(root, "D1")
    set_focus(root, "D2")
    assert (root / "D2").is_dir()

    # idempotent ensure
    path = ensure_dx_on_focus(root, "D2")
    assert path == (root / "D2").resolve()
    assert path.is_dir()


def test_deliver_split_requires_confirm(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    _enter_split_ready(root)
    with pytest.raises(ValueError, match="human --confirm"):
        deliver_split(
            root, tree=_sample_tree(), rulers=_sample_rulers(), confirm=False
        )


def test_complete_intake_requires_slots(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    _enter_split_ready(root)
    write_intake(root, empty_intake())
    with pytest.raises(ValueError, match="must be filled"):
        complete_intake(root, confirm=True)
