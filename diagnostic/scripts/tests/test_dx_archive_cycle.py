#!/usr/bin/env python3
"""Tests for cycle-based diagnostic archive (dx_archive_cycle)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dx_archive_cycle import (  # noqa: E402
    archive_other_delivered_sessions,
    cold_session_dir,
    is_session_delivered,
    resolve_session_dir,
    restore_current_session,
    run_diagnostic_cycle_archive,
)
from dx_workflow_common import session_base_dir  # noqa: E402

_PLATFORM = "cursor"
_CACHE_ROOT = Path(".cache/cursor/lulu-dev-workflow")


def _write_active_context(
    project_root: Path,
    entries: dict[str, dict[str, str]],
) -> None:
    path = project_root / _CACHE_ROOT / "active-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _write_session_state(session_dir: Path, current_state: str) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        f"---\ncurrent_state: {current_state}\n---\n",
        encoding="utf-8",
    )


def _write_domain_constraints(
    session_dir: Path,
    *,
    stage: str,
    cache_subdir: str,
) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "domain-constraints.json").write_text(
        json.dumps(
            {
                "version": 1,
                "stage": stage,
                "cache_subdir": cache_subdir,
            }
        ),
        encoding="utf-8",
    )


def _setup_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    cache_subdir: str,
    *,
    current_state: str = "InProgress",
) -> Path:
    session_dir = project_root / _CACHE_ROOT / cycle_id / cache_subdir
    _write_domain_constraints(session_dir, stage=stage, cache_subdir=cache_subdir)
    _write_session_state(session_dir, current_state)
    return session_dir


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


def test_resolve_session_dir_product_diagnostic(project_root: Path) -> None:
    cycle_id = "feat-pd"
    stage = "product-diagnostic"
    subdir = "product/diagnostic"
    _setup_session(project_root, cycle_id, stage, subdir)
    found = resolve_session_dir(project_root, cycle_id, stage, platform=_PLATFORM)
    assert found == project_root / _CACHE_ROOT / cycle_id / subdir


def test_resolve_session_dir_tech_diagnostic(project_root: Path) -> None:
    cycle_id = "feat-td"
    stage = "tech-diagnostic"
    subdir = "tech/diagnostic"
    _setup_session(project_root, cycle_id, stage, subdir)
    found = resolve_session_dir(project_root, cycle_id, stage, platform=_PLATFORM)
    assert found == project_root / _CACHE_ROOT / cycle_id / subdir


def test_is_session_delivered() -> None:
    delivered = Path("/tmp/dx-delivered")
    in_progress = Path("/tmp/dx-inprogress")
    missing = Path("/tmp/dx-missing")
    _write_session_state(delivered, "Delivered")
    _write_session_state(in_progress, "InProgress")
    assert is_session_delivered(delivered) is True
    assert is_session_delivered(in_progress) is False
    assert is_session_delivered(missing) is None


def test_restore_moves_cold_to_hot(project_root: Path) -> None:
    conv_id = "conv-restore"
    cycle_id = "feat-restore"
    stage = "product-diagnostic"
    subdir = "product/diagnostic"
    _write_active_context(
        project_root,
        {conv_id: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"}},
    )
    cold = cold_session_dir(project_root, conv_id, subdir, platform=_PLATFORM)
    _setup_session(project_root, cycle_id, stage, subdir, current_state="Delivered")
    hot = project_root / _CACHE_ROOT / cycle_id / subdir
    cold.parent.mkdir(parents=True, exist_ok=True)
    hot.rename(cold)

    ok, messages = restore_current_session(
        project_root, conv_id, platform=_PLATFORM, dry_run=False
    )
    assert ok is True
    assert hot.is_dir()
    assert not cold.exists()
    assert any("restore:" in msg for msg in messages)


def test_archive_delivered_other_conv(project_root: Path) -> None:
    current = "conv-current"
    other = "conv-other"
    cycle_id = "feat-archive"
    stage = "product-diagnostic"
    subdir = "product/diagnostic"
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": stage, "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    _setup_session(project_root, cycle_id, stage, subdir, current_state="Delivered")

    ok, _ = archive_other_delivered_sessions(
        project_root, current, platform=_PLATFORM, dry_run=False
    )
    assert ok is True
    hot = project_root / _CACHE_ROOT / cycle_id / subdir
    cold = cold_session_dir(project_root, other, subdir, platform=_PLATFORM)
    assert not hot.exists()
    assert cold.is_dir()


def test_skip_non_delivered(project_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current = "conv-current"
    other = "conv-other"
    cycle_id = "feat-skip"
    stage = "tech-diagnostic"
    subdir = "tech/diagnostic"
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": stage, "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    hot = _setup_session(project_root, cycle_id, stage, subdir, current_state="InProgress")

    ok, _ = archive_other_delivered_sessions(
        project_root, current, platform=_PLATFORM, dry_run=False
    )
    captured = capsys.readouterr()
    assert ok is True
    assert hot.exists()
    assert "非终态" in captured.out


def test_skip_exclude_conv_id(project_root: Path) -> None:
    conv_id = "conv-self"
    cycle_id = "feat-self"
    stage = "diagnostic"
    subdir = "diagnostic"
    _write_active_context(
        project_root,
        {conv_id: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"}},
    )
    hot = _setup_session(project_root, cycle_id, stage, subdir, current_state="Delivered")

    ok, _ = archive_other_delivered_sessions(
        project_root, conv_id, platform=_PLATFORM, dry_run=False
    )
    assert ok is True
    assert hot.exists()


def test_skip_non_diagnostic_stage(project_root: Path) -> None:
    current = "conv-current"
    other = "conv-plan"
    cycle_id = "feat-plan"
    stage = "tech-plan"
    subdir = "tech/plan"
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": "diagnostic", "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    hot = project_root / _CACHE_ROOT / cycle_id / subdir
    hot.mkdir(parents=True)
    _write_session_state(hot, "Delivered")

    ok, _ = archive_other_delivered_sessions(
        project_root, current, platform=_PLATFORM, dry_run=False
    )
    assert ok is True
    assert hot.exists()


def test_cold_exists_skip(project_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current = "conv-current"
    other = "conv-other"
    cycle_id = "feat-cold"
    stage = "product-diagnostic"
    subdir = "product/diagnostic"
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": stage, "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    hot = _setup_session(project_root, cycle_id, stage, subdir, current_state="Delivered")
    cold = cold_session_dir(project_root, other, subdir, platform=_PLATFORM)
    cold.mkdir(parents=True)

    ok, _ = archive_other_delivered_sessions(
        project_root, current, platform=_PLATFORM, dry_run=False
    )
    captured = capsys.readouterr()
    assert ok is True
    assert hot.exists()
    assert "冷区已存在" in captured.out


def test_dry_run_no_move(project_root: Path) -> None:
    current = "conv-current"
    other = "conv-other"
    cycle_id = "feat-dry"
    stage = "tech-diagnostic"
    subdir = "tech/diagnostic"
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": stage, "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    hot = _setup_session(project_root, cycle_id, stage, subdir, current_state="Delivered")

    rc = run_diagnostic_cycle_archive(
        project_root, current, platform=_PLATFORM, dry_run=True
    )
    assert rc == 0
    assert hot.exists()
    assert not cold_session_dir(project_root, other, subdir, platform=_PLATFORM).exists()


def test_run_archive_integration_matches_session_base_dir(project_root: Path) -> None:
    current = "conv-current"
    other = "conv-other"
    cycle_id = "feat-int"
    stage = "product-diagnostic"
    constraints_stage_path = Path(__file__).resolve().parents[3] / stage / "constraints.json"
    expected_hot = project_root / session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_stage_path,
    )
    _write_active_context(
        project_root,
        {
            current: {"cycle_id": "feat-current", "stage": stage, "cycle_type": "feature"},
            other: {"cycle_id": cycle_id, "stage": stage, "cycle_type": "feature"},
        },
    )
    _write_domain_constraints(
        expected_hot,
        stage=stage,
        cache_subdir="product/diagnostic",
    )
    _write_session_state(expected_hot, "Delivered")

    rc = run_diagnostic_cycle_archive(project_root, current, platform=_PLATFORM)
    assert rc == 0
    assert not expected_hot.exists()
    cold = cold_session_dir(project_root, other, "product/diagnostic", platform=_PLATFORM)
    assert cold.is_dir()
