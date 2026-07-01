#!/usr/bin/env python3
"""Cycle-based archive/restore for decision-family sessions.

Hot:  cache/<cycle_id>/<cache_subdir>/  (from active-context + session snapshot)
Cold: cache/_archive/<conversation_id>/<cache_subdir>/

Does not use legacy cache/decision/<conversation_id>/ layout.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from active_context_schema import read_all  # noqa: E402
from archive_common import is_valid_conv_id, read_md_field  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir  # noqa: E402

from dec_session_paths import find_session_dir, session_cache_subdir  # noqa: E402

DIAGNOSTIC_ARCHIVE_STAGES = frozenset(
    {
        "decision",
        "lulu-bet",
        "lulu-approach",
    }
)

TERMINAL_STATES = frozenset({"Delivered"})
STATE_FILE = "session-state.md"
STATE_FIELD = "current_state"


def _cache_root(platform: str | None) -> Path:
    plat = platform or detect_platform()
    return cache_dir(plat)


def resolve_session_dir(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    platform: str | None = None,
) -> Path | None:
    """Return hot session dir cache/<cycle_id>/<cache_subdir>/ if it exists."""
    root = _cache_root(platform)
    found = find_session_dir(project_root, cycle_id, stage, root)
    if found is not None:
        return found
    subdir = session_cache_subdir(project_root, cycle_id, stage, root, constraints_path=None)
    candidate = project_root / root / cycle_id / subdir
    if candidate.is_dir():
        return candidate
    return None


def _cache_subdir_from_session(session_dir: Path) -> str | None:
    dc = session_dir / "domain-constraints.json"
    if not dc.is_file():
        return None
    try:
        data = json.loads(dc.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    subdir = str(data.get("cache_subdir", "")).strip()
    return subdir or None


def resolve_cache_subdir(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    platform: str | None = None,
    session_dir: Path | None = None,
) -> str:
    if session_dir is not None:
        from_snapshot = _cache_subdir_from_session(session_dir)
        if from_snapshot:
            return from_snapshot
        root = _cache_root(platform)
        cycle_base = project_root / root / cycle_id
        try:
            return session_dir.relative_to(cycle_base).as_posix()
        except ValueError:
            pass
    root = _cache_root(platform)
    return session_cache_subdir(project_root, cycle_id, stage, root, constraints_path=None)


def cold_session_dir(
    project_root: Path,
    conversation_id: str,
    cache_subdir: str,
    *,
    platform: str | None = None,
) -> Path:
    root = _cache_root(platform)
    return project_root / root / "_archive" / conversation_id / cache_subdir


def hot_session_dir(
    project_root: Path,
    cycle_id: str,
    cache_subdir: str,
    *,
    platform: str | None = None,
) -> Path:
    root = _cache_root(platform)
    return project_root / root / cycle_id / cache_subdir


def is_session_delivered(session_dir: Path) -> bool | None:
    """Return True if Delivered, False if readable non-terminal, None if unknown."""
    state_path = session_dir / STATE_FILE
    if not state_path.is_file():
        return None
    current_state = read_md_field(state_path, STATE_FIELD, default="")
    if not current_state:
        return None
    if current_state in TERMINAL_STATES:
        return True
    return False


def _find_cold_session(
    project_root: Path,
    conversation_id: str,
    cycle_id: str,
    stage: str,
    *,
    platform: str | None = None,
) -> Tuple[Path | None, str]:
    expected_subdir = resolve_cache_subdir(
        project_root, cycle_id, stage, platform=platform, session_dir=None
    )
    cold = cold_session_dir(project_root, conversation_id, expected_subdir, platform=platform)
    if cold.is_dir():
        return cold, expected_subdir

    root = _cache_root(platform)
    archive_parent = project_root / root / "_archive" / conversation_id
    if not archive_parent.is_dir():
        return None, expected_subdir

    for dc_path in archive_parent.rglob("domain-constraints.json"):
        session_dir = dc_path.parent
        try:
            data = json.loads(dc_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("stage", "")).strip() != stage:
            continue
        subdir = resolve_cache_subdir(
            project_root,
            cycle_id,
            stage,
            platform=platform,
            session_dir=session_dir,
        )
        return session_dir, subdir
    return None, expected_subdir


def restore_current_session(
    project_root: Path,
    conversation_id: str,
    *,
    platform: str | None = None,
    dry_run: bool = False,
) -> Tuple[bool, List[str]]:
    messages: List[str] = []
    plat = platform or detect_platform()
    entries = read_all(project_root, plat)
    entry = entries.get(conversation_id)
    if entry is None:
        return True, messages

    stage = entry["stage"]
    if stage not in DIAGNOSTIC_ARCHIVE_STAGES:
        return True, messages

    cycle_id = entry["cycle_id"]
    hot_dir = resolve_session_dir(project_root, cycle_id, stage, platform=plat)
    cache_subdir = resolve_cache_subdir(
        project_root,
        cycle_id,
        stage,
        platform=plat,
        session_dir=hot_dir,
    )
    hot_path = hot_session_dir(project_root, cycle_id, cache_subdir, platform=plat)
    cold_path, _ = _find_cold_session(
        project_root, conversation_id, cycle_id, stage, platform=plat
    )

    if hot_path.is_dir():
        return True, messages
    if cold_path is None or not cold_path.is_dir():
        return True, messages

    msg = f"restore: {cold_path.as_posix()} -> {hot_path.as_posix()}"
    print(msg)
    messages.append(msg)
    if dry_run:
        return True, messages

    hot_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(cold_path), str(hot_path))
    except OSError as exc:
        print(f"错误：restore 失败：{exc}", file=sys.stderr)
        return False, messages

    _prune_empty_archive_parent(cold_path)
    return True, messages


def _prune_empty_archive_parent(cold_path: Path) -> None:
    archive_parent = cold_path.parent
    if archive_parent.exists() and not any(archive_parent.iterdir()):
        archive_parent.rmdir()
    archive_root = archive_parent.parent
    if (
        archive_root.name == "_archive"
        and archive_root.exists()
        and not any(archive_root.iterdir())
    ):
        archive_root.rmdir()


def _skip_non_delivered_msg(conv_id: str, stage: str, session_dir: Path) -> str:
    state = read_md_field(session_dir / STATE_FILE, STATE_FIELD, default="（未知）")
    return f"skip: {conv_id} — {stage} 仍为 {state}（非终态）"


def archive_other_delivered_sessions(
    project_root: Path,
    exclude_conv_id: str,
    *,
    platform: str | None = None,
    dry_run: bool = False,
) -> Tuple[bool, List[str]]:
    messages: List[str] = []
    ok = True
    plat = platform or detect_platform()
    entries = read_all(project_root, plat)

    for conv_id, entry in sorted(entries.items()):
        if not is_valid_conv_id(conv_id):
            continue
        if conv_id == exclude_conv_id:
            continue

        stage = entry["stage"]
        if stage not in DIAGNOSTIC_ARCHIVE_STAGES:
            continue

        cycle_id = entry["cycle_id"]
        hot_dir = resolve_session_dir(project_root, cycle_id, stage, platform=plat)
        if hot_dir is None:
            continue

        cache_subdir = resolve_cache_subdir(
            project_root,
            cycle_id,
            stage,
            platform=plat,
            session_dir=hot_dir,
        )
        cold_dir = cold_session_dir(project_root, conv_id, cache_subdir, platform=plat)
        terminal = is_session_delivered(hot_dir)

        if terminal is None:
            msg = f"skip: {conv_id} — 无法读取 session-state 或 current_state"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        if terminal is False:
            msg = _skip_non_delivered_msg(conv_id, stage, hot_dir)
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        if cold_dir.exists():
            msg = f"skip: {conv_id} — 冷区已存在 {cold_dir.as_posix()}"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        msg = f"archive: {hot_dir.as_posix()} -> {cold_dir.as_posix()}"
        print(msg)
        messages.append(msg)

        if dry_run:
            continue

        cold_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(hot_dir), str(cold_dir))
        except OSError as exc:
            print(f"错误：archive 失败（{conv_id}）：{exc}", file=sys.stderr)
            ok = False

    return ok, messages


def run_diagnostic_cycle_archive(
    project_root: Path,
    exclude_conv_id: str,
    *,
    platform: str | None = None,
    dry_run: bool = False,
) -> int:
    plat = platform or detect_platform()
    restored_ok, _ = restore_current_session(
        project_root,
        exclude_conv_id,
        platform=plat,
        dry_run=dry_run,
    )
    if not restored_ok:
        return 1

    archived_ok, _ = archive_other_delivered_sessions(
        project_root,
        exclude_conv_id,
        platform=plat,
        dry_run=dry_run,
    )
    if not archived_ok:
        return 1
    return 0
