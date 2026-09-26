#!/usr/bin/env python3
"""Active Session schema + resolve (archive-1.1 A3/A4/A5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_active_session_schema import (  # noqa: E402
    ACTIVE_SESSION_FILENAME,
    load_active_session,
    save_active_session,
    validate_active_session,
)
from dec_session_paths import (  # noqa: E402
    find_session_dir,
    resolve_active_session_dir,
    stage_outer_root,
)


def test_find_session_dir_matches_cycle_child_not_nested_child(tmp_path: Path) -> None:
    cycle = tmp_path / "cache" / "c1"
    stage_dir = cycle / "holder"
    nested = stage_dir / "main"
    nested.mkdir(parents=True)
    payload = json.dumps({"stage": "holder"})
    (stage_dir / "domain-constraints.json").write_text(payload, encoding="utf-8")
    (nested / "domain-constraints.json").write_text(payload, encoding="utf-8")
    found = find_session_dir(tmp_path, "c1", "holder", Path("cache"))
    assert found == stage_dir


def test_validate_active_session_ok() -> None:
    data = validate_active_session(
        {"version": "1", "session_dir": "work", "updated_at": "2026-07-29T00:00:00+00:00"}
    )
    assert data["session_dir"] == "work"


def test_validate_rejects_escape() -> None:
    with pytest.raises(ValueError, match="session_dir"):
        validate_active_session({"version": "1", "session_dir": "../x", "updated_at": "t"})


def test_save_load_roundtrip(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    save_active_session(outer, ".")
    loaded = load_active_session(outer)
    assert loaded["session_dir"] == "."
    assert (outer / ACTIVE_SESSION_FILENAME).is_file()


def test_resolve_active_session_dir_nested(tmp_path: Path) -> None:
    outer = tmp_path / "stage"
    d1 = outer / "D1"
    d1.mkdir(parents=True)
    (d1 / "gate-state.json").write_text("{}", encoding="utf-8")
    save_active_session(outer, "D1")
    assert resolve_active_session_dir(outer) == d1.resolve()


def test_resolve_active_missing_raises(tmp_path: Path) -> None:
    outer = tmp_path / "stage"
    outer.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_active_session_dir(outer)


def test_stage_outer_root_matches_session_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dec_workflow_common import CACHE_DIR, session_base_dir

    project_root = tmp_path
    cycle_id = "feature-active-outer-001"
    stage = "decision"
    monkeypatch.chdir(project_root)
    expected = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    got = stage_outer_root(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
    )
    assert got == expected.resolve()
