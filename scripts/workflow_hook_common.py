"""Shared helpers for lulu-dev-workflow preToolUse hooks."""

from __future__ import annotations

from pathlib import Path


def deny_cache_boundary(*, stage: str, cache_dir: Path, target_path: Path) -> dict:
    cache_str = cache_dir.as_posix()
    target_str = target_path.as_posix()
    user_message = (
        f"[lulu-dev-workflow] 写入被拦截：{stage} 阶段仅允许写入 workflow cache（{cache_str}）。"
        "请确认是否继续本阶段、完成交付，或切换到下一阶段。"
    )
    agent_message = (
        f"[lulu-dev-workflow] Write blocked in stage '{stage}': outside workflow cache.\n"
        f"Target: {target_str}\n"
        f"Allowed directory: {cache_str}\n"
        "STOP: Do not retry this write or attempt workarounds "
        "(Shell redirects, alternate paths, etc.).\n"
        "Inform the user what was blocked and why; "
        "wait for their instruction before proceeding."
    )
    return {
        "permission": "deny",
        "user_message": user_message,
        "agent_message": agent_message,
    }
