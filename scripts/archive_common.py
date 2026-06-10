#!/usr/bin/env python3
"""Shared archive/restore logic for lulu-dev-workflow stages."""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, List, Optional, Tuple

_PLATFORM = (
    __import__("os").environ.get("LULU_PLATFORM")
    or ("copilot" if __import__("os").environ.get("COPILOT_AGENT") else "cursor")
)
CACHE_DIR = Path(f".cache/{_PLATFORM}/lulu-dev-workflow")

_CONV_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


@dataclass(frozen=True)
class StageArchiveConfig:
    stage: str
    hot_subdir: str
    session_counter_field: str
    doc_dir_fmt: str
    terminal_states: FrozenSet[str]
    state_file: str = "workflow-state.md"
    state_field: str = "current_state"
    flat: bool = False


PRODUCT_PLAN_CONFIG = StageArchiveConfig(
    stage="product-plan",
    hot_subdir="product/plan",
    session_counter_field="active_doc",
    doc_dir_fmt="revision{}",
    terminal_states=frozenset({"Delivered"}),
)

TECH_PLAN_CONFIG = StageArchiveConfig(
    stage="tech-plan",
    hot_subdir="tech/plan",
    session_counter_field="active_doc",
    doc_dir_fmt="revision{}",
    terminal_states=frozenset({"Delivered"}),
)

TECH_WORK_ORDER_CONFIG = StageArchiveConfig(
    stage="tech-work-order",
    hot_subdir="tech/work-order",
    session_counter_field="active_doc",
    doc_dir_fmt="r{}",
    terminal_states=frozenset({"Delivered"}),
)

DIAGNOSTIC_CONFIG = StageArchiveConfig(
    stage="diagnostic",
    hot_subdir="diagnostic",
    session_counter_field="",
    doc_dir_fmt="",
    terminal_states=frozenset({"Delivered"}),
    state_file="session-state.md",
    flat=True,
)

TECH_CODE_CONFIG = StageArchiveConfig(
    stage="tech-code",
    hot_subdir="tech/code",
    session_counter_field="active_session",
    doc_dir_fmt="s{}",
    terminal_states=frozenset({"Delivered"}),
)

ALL_STAGE_CONFIGS = (
    PRODUCT_PLAN_CONFIG,
    TECH_PLAN_CONFIG,
    TECH_WORK_ORDER_CONFIG,
    DIAGNOSTIC_CONFIG,
    TECH_CODE_CONFIG,
)


def parse_frontmatter_fields(content: str) -> dict[str, str]:
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return {}
    result: dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        kv_match = re.match(r"^(\w+):\s*(.*)", line)
        if kv_match:
            result[kv_match.group(1)] = kv_match.group(2).strip()
    return result


def read_md_field(path: Path, field: str, default: str = "") -> str:
    if not path.exists():
        return default
    content = path.read_text(encoding="utf-8")
    fields = parse_frontmatter_fields(content)
    return fields.get(field, default)


def hot_root(config: StageArchiveConfig) -> Path:
    return CACHE_DIR / config.hot_subdir


def archive_dir(config: StageArchiveConfig, conversation_id: str) -> Path:
    return CACHE_DIR / "_archive" / conversation_id / config.hot_subdir


def hot_conv_dir(config: StageArchiveConfig, conversation_id: str) -> Path:
    return hot_root(config) / conversation_id


def is_valid_conv_id(name: str) -> bool:
    if name.startswith("_"):
        return False
    return bool(_CONV_ID_RE.match(name) or _SLUG_RE.match(name))


def list_conv_ids(hot_root_path: Path) -> List[str]:
    if not hot_root_path.is_dir():
        return []
    result: List[str] = []
    for entry in sorted(hot_root_path.iterdir()):
        if not entry.is_dir():
            continue
        if is_valid_conv_id(entry.name):
            result.append(entry.name)
    return result


def _active_doc_dir(conv_dir: Path, config: StageArchiveConfig, active_round: int) -> Path:
    return conv_dir / config.doc_dir_fmt.format(active_round)


def is_conv_terminal(conv_dir: Path, config: StageArchiveConfig) -> Optional[bool]:
    """
    Return True if conv is in a terminal state, False if readable and non-terminal,
    None if state cannot be determined.
    """
    if config.flat:
        state_path = conv_dir / config.state_file
        if not state_path.exists():
            return None
        current_state = read_md_field(state_path, config.state_field, default="")
        if not current_state:
            return None
        if current_state in config.terminal_states:
            return True
        return False

    ss_path = conv_dir / "session-state.md"
    if not ss_path.exists():
        return None
    active_raw = read_md_field(ss_path, config.session_counter_field, default="")
    if not active_raw:
        return None
    try:
        active_round = int(active_raw)
    except ValueError:
        return None

    ws_path = _active_doc_dir(conv_dir, config, active_round) / config.state_file
    if not ws_path.exists():
        return None
    current_state = read_md_field(ws_path, config.state_field, default="")
    if not current_state:
        return None
    if current_state in config.terminal_states:
        return True
    return False


def restore_current_if_needed(
    project_root: Path,
    config: StageArchiveConfig,
    current_conv_id: str,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    hot_dir = project_root / hot_conv_dir(config, current_conv_id)
    cold_dir = project_root / archive_dir(config, current_conv_id)

    if hot_dir.exists():
        return True, ""
    if not cold_dir.exists():
        return True, ""

    msg = f"restore: {cold_dir.as_posix()} -> {hot_dir.as_posix()}"
    print(msg)
    if dry_run:
        return True, msg

    hot_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(cold_dir), str(hot_dir))
    except OSError as exc:
        print(f"错误：restore 失败：{exc}", file=sys.stderr)
        return False, msg

    archive_parent = cold_dir.parent
    if archive_parent.exists() and not any(archive_parent.iterdir()):
        archive_parent.rmdir()
    return True, msg


def _skip_non_terminal_msg(conv_id: str, config: StageArchiveConfig, conv_dir: Path) -> str:
    if config.flat:
        state_path = conv_dir / config.state_file
        state = read_md_field(state_path, config.state_field, default="（未知）")
        return f"skip: {conv_id} — {config.stage} 仍为 {state}（非终态）"

    ss_path = conv_dir / "session-state.md"
    active_raw = read_md_field(ss_path, config.session_counter_field, default="")
    try:
        active_round = int(active_raw)
    except ValueError:
        active_round = 0
    ws_path = _active_doc_dir(conv_dir, config, active_round) / config.state_file
    state = read_md_field(ws_path, config.state_field, default="（未知）")
    return f"skip: {conv_id} — {config.stage} active 轮次仍为 {state}（非终态）"


def archive_terminal_convs(
    project_root: Path,
    config: StageArchiveConfig,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> Tuple[bool, List[str]]:
    stage_root = project_root / hot_root(config)
    messages: List[str] = []
    ok = True

    for conv_id in list_conv_ids(stage_root):
        if conv_id == exclude_conv_id:
            continue

        hot_dir = stage_root / conv_id
        cold_dir = project_root / archive_dir(config, conv_id)
        terminal = is_conv_terminal(hot_dir, config)

        if terminal is None:
            msg = f"skip: {conv_id} — 无法读取 session-state 或 workflow-state"
            print(f"警告：{msg}")
            messages.append(msg)
            continue

        if terminal is False:
            msg = _skip_non_terminal_msg(conv_id, config, hot_dir)
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


def run_archive(
    project_root: Path,
    config: StageArchiveConfig,
    exclude_conv_id: str,
    dry_run: bool = False,
) -> int:
    restored_ok, _ = restore_current_if_needed(
        project_root, config, exclude_conv_id, dry_run=dry_run
    )
    if not restored_ok:
        return 1

    archived_ok, _ = archive_terminal_convs(
        project_root, config, exclude_conv_id, dry_run=dry_run
    )
    if not archived_ok:
        return 1
    return 0
