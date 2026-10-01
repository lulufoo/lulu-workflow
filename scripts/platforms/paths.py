"""Per-platform project paths and hook install command templates."""

from __future__ import annotations

from pathlib import Path

from platforms.registry import PLATFORM_PATHS, SKILL_NAME, resolve_workflow_dir

HOOK_PLATFORMS = frozenset({"cursor", "copilot", "claude"})

_HOOKS_CONFIG_PATH: dict[str, Path] = {
    "cursor": Path(".cursor/hooks.json"),
    "copilot": Path(".github/hooks/hooks.json"),
    "claude": Path(".claude/settings.json"),
}

_GITIGNORE_ENTRY: dict[str, str] = {
    "cursor": ".cursor",
    "claude": ".claude",
}

SKILL_INSTALL_COMMAND_ROOT = f"~/.agents/skills/{SKILL_NAME}"

CLAUDE_PRE_TOOL_USE_MATCHER = "Write|Edit|Read|Bash"
CURSOR_PRE_TOOL_USE_MATCHER = "Write|Edit|Read|Shell"


def workflow_dir(platform: str) -> Path:
    return resolve_workflow_dir(platform)


def cache_dir(platform: str) -> Path:
    return PLATFORM_PATHS[platform]["cache_dir"]


def hooks_config_path(platform: str) -> Path:
    return _HOOKS_CONFIG_PATH[platform]


def gitignore_entry(platform: str) -> str | None:
    return _GITIGNORE_ENTRY.get(platform)


def hook_guard_command(platform: str) -> str:
    """Return hooks.json command string for the installed skill hook entry."""
    command = f"python3 {SKILL_INSTALL_COMMAND_ROOT}/scripts/hook/hook_guard.py"
    if platform in ("copilot", "claude"):
        command += f" --platform {platform}"
    return command


def hook_prompt_command(platform: str) -> str:
    """Return beforeSubmitPrompt command for externalPathGuard.sessionAllow."""
    return (
        f"python3 {SKILL_INSTALL_COMMAND_ROOT}/scripts/hook/hook_prompt.py"
        f" --platform {platform}"
    )
