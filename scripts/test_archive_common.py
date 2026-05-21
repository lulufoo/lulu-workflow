#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from archive_common import (  # noqa: E402
    ALL_STAGE_CONFIGS,
    CODE_CONFIG,
    DIAGNOSTIC_CONFIG,
    PRODUCT_CONFIG,
    WORK_ORDER_CONFIG,
    archive_dir,
    hot_conv_dir,
    hot_root,
    is_conv_terminal,
    is_valid_conv_id,
    list_conv_ids,
    run_archive,
)


def write_md_field(path: Path, **fields: str) -> None:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines.append("---\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_workflow_state(path: Path, current_state: str) -> None:
    write_md_field(path, version="1", current_state=current_state)


def _write_session_state(path: Path, counter_field: str, value: int) -> None:
    write_md_field(path, version="1", **{counter_field: str(value)})


def _setup_rounded_conv(
    root: Path,
    config,
    conv_id: str,
    active: int,
    current_state: str,
    extra_rounds: Optional[List[Tuple[int, str]]] = None,
) -> Path:
    conv_dir = root / hot_conv_dir(config, conv_id)
    _write_session_state(
        conv_dir / "session-state.md",
        config.session_counter_field,
        active,
    )
    _write_workflow_state(
        conv_dir / config.doc_dir_fmt.format(active) / config.state_file,
        current_state,
    )
    for rnd, state in extra_rounds or []:
        _write_workflow_state(
            conv_dir / config.doc_dir_fmt.format(rnd) / config.state_file,
            state,
        )
    return conv_dir


@pytest.fixture
def project_root(tmp_path):
    cache = tmp_path / ".cache" / "lulu-dev-workflow"
    cache.mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_terminal_archives_other_conv(project_root, config):
    current = "current-conv"
    other = "other-conv"
    if config.flat:
        other_dir = project_root / hot_conv_dir(config, other)
        write_md_field(other_dir / "session-state.md", current_state="Delivered")
    else:
        terminal = "Completed" if config is CODE_CONFIG else "Delivered"
        _setup_rounded_conv(project_root, config, other, 1, terminal)

    rc = run_archive(project_root, config, exclude_conv_id=current)
    assert rc == 0
    assert not (project_root / hot_conv_dir(config, other)).exists()
    assert (project_root / archive_dir(config, other)).exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_non_terminal_skips(project_root, config):
    other = "other-conv"
    if config.flat:
        other_dir = project_root / hot_conv_dir(config, other)
        write_md_field(other_dir / "session-state.md", current_state="InProgress")
    elif config is CODE_CONFIG:
        _setup_rounded_conv(project_root, config, other, 2, "Executing", extra_rounds=[(1, "Completed")])
    else:
        _setup_rounded_conv(project_root, config, other, 1, "Drafting")

    rc = run_archive(project_root, config, exclude_conv_id="current-conv")
    assert rc == 0
    assert (project_root / hot_conv_dir(config, other)).exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_current_conv_never_archived(project_root, config):
    current = "current-conv"
    if config.flat:
        conv_dir = project_root / hot_conv_dir(config, current)
        write_md_field(conv_dir / "session-state.md", current_state="Delivered")
    else:
        terminal = "Completed" if config is CODE_CONFIG else "Delivered"
        _setup_rounded_conv(project_root, config, current, 1, terminal)

    run_archive(project_root, config, exclude_conv_id=current)
    assert (project_root / hot_conv_dir(config, current)).exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_restore_then_continue(project_root, config):
    current = "current-conv"
    cold = project_root / archive_dir(config, current)
    cold.mkdir(parents=True)
    marker = cold / ("decision-doc.md" if config.flat else config.doc_dir_fmt.format(1))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ok", encoding="utf-8")

    rc = run_archive(project_root, config, exclude_conv_id=current)
    assert rc == 0
    assert (project_root / hot_conv_dir(config, current)).exists()
    assert not cold.exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_cold_conflict_skips(project_root, config):
    other = "other-conv"
    if config.flat:
        write_md_field(
            (project_root / hot_conv_dir(config, other) / "session-state.md"),
            current_state="Delivered",
        )
    else:
        terminal = "Completed" if config is CODE_CONFIG else "Delivered"
        _setup_rounded_conv(project_root, config, other, 1, terminal)

    cold = project_root / archive_dir(config, other)
    cold.mkdir(parents=True)
    (cold / "conflict.txt").write_text("x", encoding="utf-8")

    run_archive(project_root, config, exclude_conv_id="current-conv")
    assert (project_root / hot_conv_dir(config, other)).exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_missing_state_skips(project_root, config):
    other = "other-conv"
    (project_root / hot_conv_dir(config, other)).mkdir(parents=True)
    if not config.flat:
        _write_session_state(
            project_root / hot_conv_dir(config, other) / "session-state.md",
            config.session_counter_field,
            1,
        )

    run_archive(project_root, config, exclude_conv_id="current-conv")
    assert (project_root / hot_conv_dir(config, other)).exists()


@pytest.mark.parametrize("config", ALL_STAGE_CONFIGS)
def test_dry_run_no_disk_change(project_root, config):
    other = "other-conv"
    if config.flat:
        write_md_field(
            project_root / hot_conv_dir(config, other) / "session-state.md",
            current_state="Delivered",
        )
    else:
        terminal = "Completed" if config is CODE_CONFIG else "Delivered"
        _setup_rounded_conv(project_root, config, other, 1, terminal)

    hot = project_root / hot_conv_dir(config, other)
    run_archive(project_root, config, exclude_conv_id="current-conv", dry_run=True)
    assert hot.exists()
    assert not (project_root / archive_dir(config, other)).exists()


def test_slug_conv_id_listed_and_archived(project_root):
    slug = "p4-tauri-migration"
    _setup_rounded_conv(project_root, WORK_ORDER_CONFIG, slug, 1, "Delivered")
    assert slug in list_conv_ids(project_root / hot_root(WORK_ORDER_CONFIG))
    run_archive(project_root, WORK_ORDER_CONFIG, exclude_conv_id="other")
    assert (project_root / archive_dir(WORK_ORDER_CONFIG, slug)).exists()


def test_ready_for_delivery_skips(project_root):
    _setup_rounded_conv(project_root, PRODUCT_CONFIG, "other", 1, "ReadyForDelivery")
    run_archive(project_root, PRODUCT_CONFIG, exclude_conv_id="current")
    assert (project_root / hot_conv_dir(PRODUCT_CONFIG, "other")).exists()


def test_diagnostic_no_session_state_skips(project_root):
    other = "legacy-conv"
    conv = project_root / hot_conv_dir(DIAGNOSTIC_CONFIG, other)
    conv.mkdir(parents=True)
    (conv / "decision-doc.md").write_text("# doc", encoding="utf-8")
    assert is_conv_terminal(conv, DIAGNOSTIC_CONFIG) is None
    run_archive(project_root, DIAGNOSTIC_CONFIG, exclude_conv_id="current")
    assert conv.exists()


def test_is_valid_conv_id():
    assert is_valid_conv_id("5e40148d-33b4-4f36-a79d-1d17a77def1c")
    assert is_valid_conv_id("p4-tauri-migration")
    assert not is_valid_conv_id("_agents")
    assert not is_valid_conv_id("")
