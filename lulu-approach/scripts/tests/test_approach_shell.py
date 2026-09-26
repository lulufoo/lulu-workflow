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
enter_package_ready = _ctrl.enter_package_ready
confirm_seal = _ctrl.confirm_seal
load_shell = _schema.load_shell
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


def test_init_shell_starts_session(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    shell = init_shell(root)
    assert shell["macro_state"] == "Session"
    loaded = load_shell(root)
    assert loaded["macro_state"] == "Session"
    assert (root / "discussion-pointer.json").is_file()


def test_session_to_package_ready(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    with pytest.raises(ValueError, match="session is not Completed"):
        enter_package_ready(root)
    _write_delivered(root)
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"
    with pytest.raises(ValueError, match="human --confirm required"):
        confirm_seal(root, confirm=False)


def test_confirm_seal_registers_decision_package_ref(tmp_path: Path) -> None:
    """PackageReady + confirm registers decision-package in delivered-refs."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    root = project_root / "approach-root" / "lulu-approach"
    cycle_id = "feat-approach-seal"
    init_shell(root)
    _write_delivered(root)
    enter_package_ready(root)
    (root / "decision-doc.md").write_text(
        "{}\n",
        encoding="utf-8",
    )

    residual = source_package_path(root)
    residual.write_text("{}\n", encoding="utf-8")
    result = confirm_seal(
        root,
        confirm=True,
        cycle_id=cycle_id,
        project_root=project_root,
    )
    assert result["delivered"] is True
    pkg = decision_package_path(root)
    assert pkg.is_file()
    assert result["decision_package"] == str(pkg.resolve())
    assert result["next_steps"] == ["lulu-design", "lulu-plan"]
    assert not residual.is_file()

    refs_path = delivered_refs_file_path(cycle_id, project_root)
    assert refs_path.is_file()
    refs = load_delivered_refs_file(cycle_id, project_root)
    entry = refs["entries"]["lulu-approach"]
    assert entry["path"] == str(pkg.resolve())
    assert entry["artifact"] == "decision-package"
    assert entry["revision"] == 1
    assert entry["profile_id"] == "lulu-approach"
    assert entry["source_workflow_state"] == str(shell_path(root).resolve())
    decision_package = json.loads(pkg.read_text(encoding="utf-8"))
    assert decision_package["main"]["decision_doc_path"] == "decision-doc.md"
    assert "slices" not in decision_package


def test_confirm_seal_rolls_back_refs_keeps_decision_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    root = project_root / "lulu-approach"
    init_shell(root)
    _write_delivered(root)
    enter_package_ready(root)
    (root / "decision-doc.md").write_text(
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

    assert decision_package_path(root).is_file()
    assert not source_package_path(root).exists()
    assert not delivered_refs_file_path("feat-approach-rollback", project_root).exists()


def test_enter_package_ready_cli_has_no_path_flag() -> None:
    parser = _ctrl._build_parser()
    parser.parse_args(["--approach-root", "/tmp/x", "enter-package-ready"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["--approach-root", "/tmp/x", "enter-package-ready", "--path", "A"]
        )

