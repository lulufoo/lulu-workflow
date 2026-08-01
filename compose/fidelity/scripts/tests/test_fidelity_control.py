#!/usr/bin/env python3
"""Tests for fidelity_control gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_FIDELITY = Path(__file__).resolve().parents[1]
_CTL = _FIDELITY / "fidelity_control.py"
_COMPOSE_SCRIPTS = _FIDELITY.parents[1] / "scripts"

if str(_COMPOSE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_COMPOSE_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import DeliveredRef  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    load_discussion_pointer,
    save_discussion_pointer,
)
from resolved_refs_schema import write_resolved_refs  # noqa: E402
from scope_package_convert import convert_scope_package  # noqa: E402
from scope_package_schema import build_scope_package, save_scope_package  # noqa: E402


def _run(revision: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CTL), "--revision-dir", str(revision), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_require_fails_without_state(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    result = _run(rev, "require-for-derive")
    assert result.returncode != 0
    assert "fidelity gate missing" in result.stderr


def test_mark_passed_opens_gate(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    assert _run(rev, "init", "--intake", "atomize").returncode == 0
    assert _run(rev, "mark-passed").returncode == 0
    result = _run(rev, "require-for-derive")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"


def test_mark_skipped_is_not_available(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    result = _run(rev, "mark-skipped", "--reason", "unit-import")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def _seed_scope_package_revision(tmp_path: Path) -> tuple[Path, str, str]:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = str((tmp_path / "D1" / "source.json").resolve())
    f2 = str((tmp_path / "D2" / "source.json").resolve())
    (tmp_path / "D1").mkdir()
    (tmp_path / "D2").mkdir()
    Path(f1).write_text('{"id":"D1"}\n', encoding="utf-8")
    Path(f2).write_text('{"id":"D2"}\n', encoding="utf-8")
    pkg = build_scope_package(
        slices=[
            {"id": "L1", "title": "Auth", "source_path": f1, "source_id": "D1"},
            {"id": "L2", "title": "Billing", "source_path": f2, "source_id": "D2"},
        ]
    )
    pkg_path = save_scope_package(rev, pkg)
    convert_scope_package(rev, scope_package_path=pkg_path)
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-plan",
        run_mode="greenfield",
        scope_ref=DeliveredRef(
            type="lulu-design",
            path=str(pkg_path.resolve()),
            artifact="scope-package",
        ),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    return rev, f1, f2


def test_paths_binds_focus_l_source_not_scope_package(tmp_path: Path) -> None:
    rev, f1, f2 = _seed_scope_package_revision(tmp_path)
    result = _run(rev, "paths")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "scope_doc" not in payload
    assert payload["source_path"] == f1
    assert payload["source_path"] != str((rev / "scope-package.json").resolve())
    assert payload["source_path"] != f2


def test_paths_follows_focus_switch_to_l2(tmp_path: Path) -> None:
    rev, f1, f2 = _seed_scope_package_revision(tmp_path)
    pointer = load_discussion_pointer(rev)
    pointer["focus"] = "L2"
    save_discussion_pointer(rev, pointer)
    result = _run(rev, "paths")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["source_path"] == f2
    assert payload["source_path"] != f1


def test_paths_missing_mirror_fails_hard(tmp_path: Path) -> None:
    rev, _f1, _f2 = _seed_scope_package_revision(tmp_path)
    (rev / "L1" / "scope-ref.json").unlink()
    result = _run(rev, "paths")
    assert result.returncode != 0
    assert "missing L source_path mirror" in result.stderr


def test_paths_non_scope_package_uses_resolved_scope_ref(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    prose = tmp_path / "design-doc.md"
    prose.write_text("# design\n", encoding="utf-8")
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-plan",
        run_mode="greenfield",
        scope_ref=DeliveredRef(
            type="lulu-design",
            path=str(prose.resolve()),
            artifact="compose-doc",
        ),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    result = _run(rev, "paths")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["source_path"] == str(prose.resolve())
    assert "scope_doc" not in payload
