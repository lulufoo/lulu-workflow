"""Shared deny responses for preToolUse rwGuard."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from workflow_stop import agent_stop_message  # noqa: E402

__all__ = ["agent_stop_message", "deny_cache_boundary", "deny_rw_boundary"]


def deny_rw_boundary(
    *,
    stage: str,
    tool_kind: str,
    allowed_dirs: list[Path],
    target_path: Path,
) -> dict:
    allowed_text = ", ".join(path.as_posix() for path in allowed_dirs) or "(none)"
    target_str = target_path.as_posix()
    user_message = (
        f"[lulu-dev-workflow] {tool_kind} 被拦截：{stage} 阶段仅允许访问 {allowed_text}。"
        "请确认是否继续本阶段、完成交付，或切换到下一阶段。"
    )
    agent_message = agent_stop_message(
        f"[lulu-dev-workflow] {tool_kind} blocked in stage '{stage}': outside allowed directories.\n"
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


def deny_cache_boundary(*, stage: str, cache_dir: Path, target_path: Path) -> dict:
    """Backward-compatible wrapper for stage hook_guard callers."""
    return deny_rw_boundary(
        stage=stage,
        tool_kind="Write",
        allowed_dirs=[cache_dir.resolve()],
        target_path=target_path,
    )
