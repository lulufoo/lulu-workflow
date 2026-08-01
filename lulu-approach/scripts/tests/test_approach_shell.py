#!/usr/bin/env python3
"""Tests for approach outer shell (archive-1.0 P2.shell)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_schema = _load("approach_shell_schema", _SCHEMA / "approach_shell_schema.py")
_layout = _load("approach_layout", _SCRIPTS / "approach_layout.py")

# control imports siblings via sys.path; load after schema/layout are importable
for _p in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
_ctrl = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")

from cycle_delivered_refs import (  # noqa: E402
    delivered_refs_file_path,
    load_delivered_refs_file,
)

init_shell = _ctrl.init_shell
enter_split = _ctrl.enter_split
enter_working = _ctrl.enter_working
enter_package_ready = _ctrl.enter_package_ready
commit_focus = _ctrl.commit_focus
set_focus = _ctrl.set_focus
mark_node_delivered = _ctrl.mark_node_delivered
mark_split_delivered = _ctrl.mark_split_delivered
confirm_seal = _ctrl.confirm_seal
load_shell = _schema.load_shell
main_session_dir = _layout.main_session_dir
shell_path = _schema.shell_path
decision_package_path = _layout.decision_package_path
source_package_path = _layout.source_package_path


def _write_delivered(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: Delivered\nupdated_at: 2026-07-29T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _write_in_progress(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: InProgress\nupdated_at: 2026-07-29T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def test_init_shell_starts_main(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    shell = init_shell(root)
    assert shell["macro_state"] == "Main"
    assert shell["focus"] is None
    assert shell["by_id"] == {}
    loaded = load_shell(root)
    assert loaded["macro_state"] == "Main"
    assert (root / "main").is_dir()
    assert (root / "discussion-pointer.json").is_file()


def test_main_to_split_requires_main_delivered(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    with pytest.raises(ValueError, match="main is not Completed"):
        enter_split(root)
    _write_delivered(main_session_dir(root))
    shell = enter_split(root)
    assert shell["macro_state"] == "Split"
    assert shell["split_delivered"] is False


def test_main_to_package_ready_no_split(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    with pytest.raises(ValueError, match="main is not Completed"):
        enter_package_ready(root)
    _write_delivered(main_session_dir(root))
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"
    with pytest.raises(ValueError, match="human --confirm required"):
        confirm_seal(root, confirm=False)


def test_confirm_seal_registers_source_package_ref(tmp_path: Path) -> None:
    """PackageReady + confirm delivers a committed source package."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    root = project_root / "approach-root" / "lulu-approach"
    cycle_id = "feat-approach-seal"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_package_ready(root)
    (main_session_dir(root) / "decision-fact.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    assert not source_package_path(root).is_file()
    result = confirm_seal(
        root,
        confirm=True,
        cycle_id=cycle_id,
        project_root=project_root,
    )
    assert result["delivered"] is True
    pkg = source_package_path(root)
    assert pkg.is_file()
    assert result["source_package"] == str(pkg.resolve())

    refs_path = delivered_refs_file_path(cycle_id, project_root)
    assert refs_path.is_file()
    refs = load_delivered_refs_file(cycle_id, project_root)
    entry = refs["entries"]["lulu-approach"]
    assert entry["path"] == str(pkg.resolve())
    assert entry["artifact"] == "source-package"
    assert entry["revision"] == 1
    assert entry["profile_id"] == "lulu-approach"
    assert entry["source_workflow_state"] == str(shell_path(root).resolve())
    source_package = json.loads(pkg.read_text(encoding="utf-8"))
    assert source_package["commit_status"] == "committed"
    assert source_package["slices"] == [
        {
            "id": "L1",
            "title": "main",
            "source_path": "main/decision-fact.json",
            "source_id": "main",
        }
    ]


def test_confirm_seal_rolls_back_source_package_when_ref_registration_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    root = project_root / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_package_ready(root)
    (main_session_dir(root) / "decision-fact.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    def fail_record(*args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError("record failed")

    monkeypatch.setattr(_ctrl, "record_delivered_ref", fail_record)
    with pytest.raises(RuntimeError, match="record failed"):
        confirm_seal(
            root,
            confirm=True,
            cycle_id="feat-approach-rollback",
            project_root=project_root,
        )

    assert not source_package_path(root).exists()
    assert not delivered_refs_file_path("feat-approach-rollback", project_root).exists()


def test_confirm_seal_split_requires_slice_artifacts(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    root = project_root / "lulu-approach"
    cycle_id = "feat-approach-split-seal"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1"], focus="D1")
    mark_node_delivered(root, "D1")
    enter_package_ready(root)

    # Existing package with non-empty slices but missing on-disk artifacts → fail
    from approach_split_control import conventional_main_paths, conventional_slice_paths
    from decision_package_schema import build_decision_package, save_decision_package

    save_decision_package(
        root,
        build_decision_package(
            main=conventional_main_paths(),
            slices=[
                {
                    "id": "D1",
                    "title": "slice one",
                    **conventional_slice_paths("D1"),
                }
            ],
            status="package_ready",
        ),
    )
    with pytest.raises(ValueError, match="missing source artifact"):
        confirm_seal(
            root,
            confirm=True,
            cycle_id=cycle_id,
            project_root=project_root,
        )

    (root / "D1").mkdir(parents=True, exist_ok=True)
    (root / "D1" / "decision-fact.json").write_text("{}\n", encoding="utf-8")
    (root / "D1" / "decision-doc.md").write_text("# D1\n", encoding="utf-8")
    result = confirm_seal(
        root,
        confirm=True,
        cycle_id=cycle_id,
        project_root=project_root,
    )
    assert result["delivered"] is True
    entry = load_delivered_refs_file(cycle_id, project_root)["entries"]["lulu-approach"]
    assert entry["artifact"] == "source-package"


def test_split_working_package_ready_path(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    with pytest.raises(ValueError, match="Split is not completed"):
        enter_working(root, ["D1", "D2"])
    mark_split_delivered(root)
    shell = enter_working(root, ["D1", "D2"], focus="D1")
    assert shell["macro_state"] == "Working"
    assert shell["focus"] == "D1"
    assert shell["by_id"]["D1"]["phase"] == "in_progress"
    assert shell["by_id"]["D2"]["phase"] == "pending"
    # S3=B: only focused Dx/ exists after enter_working
    assert (root / "D1").is_dir()
    assert not (root / "D2").exists()

    with pytest.raises(ValueError, match="not all children Completed"):
        enter_package_ready(root)

    mark_node_delivered(root, "D1")
    mark_node_delivered(root, "D2")
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"


def test_commit_focus_rejects_mid_working_switch(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2"], focus="D1")

    with pytest.raises(ValueError, match="not Completed"):
        commit_focus(root, "D2")

    shell = commit_focus(root, "D1")
    assert shell["focus"] == "D1"

    mark_node_delivered(root, "D1")
    shell = commit_focus(root, "D2")
    assert shell["focus"] == "D2"
    assert shell["by_id"]["D2"]["phase"] == "in_progress"


def test_commit_focus_switch_via_session_state_delivered_stub(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2"], focus="D1")
    _write_in_progress(root / "D1")
    with pytest.raises(ValueError, match="not Completed"):
        commit_focus(root, "D2")
    _write_delivered(root / "D1")
    shell = commit_focus(root, "D2")
    assert shell["focus"] == "D2"


def test_set_focus_is_retired_in_python_and_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2"], focus="D1")

    with pytest.raises(ValueError, match="retired.*enter-node"):
        set_focus(root, "D2")

    assert _ctrl.main(
        ["--approach-root", str(root), "set-focus", "--node-id", "D2"]
    ) == 1
    assert "enter-node" in capsys.readouterr().err


def test_cannot_enter_split_from_working(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1"], focus="D1")
    with pytest.raises(ValueError, match="enter_split requires macro_state=Main"):
        enter_split(root)
