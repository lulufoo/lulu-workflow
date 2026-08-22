#!/usr/bin/env python3
"""Tests for tech_plan_profile_control materialize."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
_START = _SCRIPTS_ROOT / "start"
for _p in (_KERNEL_TESTS, _START):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from tech_plan_profile_control import main, materialize_profile  # noqa: E402
from cycle_delivered_refs import record_delivered_ref  # noqa: E402
from workflow_common import CACHE_DIR  # noqa: E402

_CYCLE = "feat-plan-profile"


def _write_file(tmp_path: Path, rel: str, content: str = "# stub\n") -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _seed_ref(tmp_path: Path, delivered_type: str, rel: str) -> Path:
    doc = _write_file(tmp_path, rel)
    record_delivered_ref(
        _CYCLE,
        tmp_path,
        delivered_type=delivered_type,
        path=str(doc.resolve()),
        revision=1,
        profile_id=delivered_type,
        source_workflow_state=str(doc.resolve()),
    )
    return doc


def _assert_instance(path: Path, tmp_path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pipeline"]["inductive"] is True
    assert path == (
        tmp_path.resolve() / CACHE_DIR / _CYCLE / "lulu-plan" / "compose-profile.json"
    )
    return data


def test_writes_inductive_true_without_upstream(tmp_path: Path) -> None:
    path = materialize_profile(_CYCLE, tmp_path)
    _assert_instance(path, tmp_path)


def test_design_upstream_writes_inductive_true(tmp_path: Path) -> None:
    _seed_ref(tmp_path, "lulu-design", "design/design-doc.md")
    path = materialize_profile(_CYCLE, tmp_path)
    _assert_instance(path, tmp_path)


def test_approach_only_writes_inductive_true(tmp_path: Path) -> None:
    _seed_ref(tmp_path, "lulu-approach", "approach/decision-doc.md")
    path = materialize_profile(_CYCLE, tmp_path)
    _assert_instance(path, tmp_path)


def test_design_and_approach_writes_inductive_true(tmp_path: Path) -> None:
    _seed_ref(tmp_path, "lulu-design", "design/design-doc.md")
    _seed_ref(tmp_path, "lulu-approach", "approach/decision-doc.md")
    path = materialize_profile(_CYCLE, tmp_path)
    _assert_instance(path, tmp_path)


def test_does_not_rewrite_authoring_template(tmp_path: Path) -> None:
    template = _WORKFLOW_ROOT / "lulu-plan" / "compose-profile.json"
    before = template.read_text(encoding="utf-8")
    materialize_profile(_CYCLE, tmp_path)
    assert template.read_text(encoding="utf-8") == before
    assert json.loads(before)["pipeline"]["inductive"] is True


def test_overwrite_and_cli_stdout(tmp_path: Path, capsys) -> None:
    first = materialize_profile(_CYCLE, tmp_path)
    _seed_ref(tmp_path, "lulu-design", "design/design-doc.md")
    code = main(["--project-root", str(tmp_path), "--cycle-id", _CYCLE])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == first.as_posix()
    data = json.loads(first.read_text(encoding="utf-8"))
    assert data["pipeline"]["inductive"] is True
