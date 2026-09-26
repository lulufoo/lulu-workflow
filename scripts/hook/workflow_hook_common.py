"""Shared deny responses for preToolUse path guards."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from workflow_stop import agent_stop_message  # noqa: E402

__all__ = [
    "agent_stop_message",
    "deny_cache_boundary",
    "deny_external_path_guard",
    "deny_internal_path_guard",
    "deny_rw_boundary",
]


def deny_internal_path_guard(
    *,
    stage: str,
    tool_kind: str,
    allowed_dirs: list[Path],
    target_path: Path,
) -> dict:
    allowed_text = ", ".join(path.as_posix() for path in allowed_dirs) or "(none)"
    target_str = target_path.as_posix()
    user_message = (
        f"[lulu-workflow] {tool_kind} 被拦截：{stage} 阶段仅允许访问 {allowed_text}。"
        "请确认是否继续本阶段、完成交付，或切换到下一阶段。"
    )
    agent_message = agent_stop_message(
        f"[lulu-workflow] {tool_kind} blocked in stage '{stage}': "
        "outside internalPathGuard allowed directories.\n"
        f"Target: {target_str}\n"
        f"Allowed directories: {allowed_text}",
        forbidden=f"this {tool_kind.lower()}",
        workarounds="Shell redirects, alternate paths, etc.",
    )
    return {
        "permission": "deny",
        "user_message": user_message,
        "agent_message": agent_message,
    }


# Backward-compatible alias.
deny_rw_boundary = deny_internal_path_guard


def deny_external_path_guard(*, tool_kind: str, target_path: Path) -> dict:
    target_str = target_path.as_posix()
    user_message = (
        f"[lulu-workflow] {tool_kind} 被拦截：目标在仓库外且未列入 "
        "externalPathGuard 允许列表（含 sessionAllow）。"
    )
    agent_message = agent_stop_message(
        f"[lulu-workflow] {tool_kind} blocked by externalPathGuard.\n"
        f"Target: {target_str}",
        forbidden=f"this {tool_kind.lower()}",
        workarounds="Add the path to externalPathGuard allowlists, or mention it in the prompt when sessionAllow is on.",
    )
    return {
        "permission": "deny",
        "user_message": user_message,
        "agent_message": agent_message,
    }


def deny_cache_boundary(*, stage: str, cache_dir: Path, target_path: Path) -> dict:
    """Backward-compatible wrapper for stage hook_guard callers."""
    return deny_internal_path_guard(
        stage=stage,
        tool_kind="Write",
        allowed_dirs=[cache_dir.resolve()],
        target_path=target_path,
    )
