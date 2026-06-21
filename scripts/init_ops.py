#!/usr/bin/env python3
"""Project-level init operations for lulu-dev-workflow."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from subagent_config import ensure_platform_config  # noqa: E402

HOOK_DIR = SCRIPTS_DIR / "hook"
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))
from hook_config_schema import ensure_hook_config  # noqa: E402
from platforms.init.register import register_hook  # noqa: E402

SUB_WORKFLOWS = ["product-arch", "tech-arch", "tech-plan", "tech-work-order", "tech-code"]


def ensure_copilot_platform_config(project_root: Path) -> None:
    ensure_platform_config(project_root, platform="copilot")


_INIT_SCRIPT = {
    "tech-code": "tc_init.py",
    "product-arch": "pa_init.py",
    "tech-arch": "ta_init.py",
    "tech-work-order": "two_init.py",
}


def _init_script(sub: str) -> Path:
    scripts = SKILL_ROOT / sub / "scripts"
    preferred = _INIT_SCRIPT.get(sub, "init.py")
    path = scripts / preferred
    if path.is_file():
        return path
    return scripts / "init.py"


def run_init_project(project_root: Path, platform: str) -> int:
    for sub in SUB_WORKFLOWS:
        init_py = _init_script(sub)
        if not init_py.exists():
            print(f"[lulu-dev-workflow init] WARNING: {init_py} not found, skipping.")
            continue
        print(f"\n[lulu-dev-workflow init] Running {sub} init...")
        result = subprocess.run(
            [sys.executable, str(init_py), "--project-root", str(project_root)],
            env={**os.environ, "LULU_PLATFORM": platform},
            check=False,
        )
        if result.returncode != 0:
            print(f"[lulu-dev-workflow init] ERROR: {sub} init failed (exit {result.returncode}).")
            return result.returncode

    ensure_platform_config(project_root, platform=platform)

    hook_command = register_hook(project_root, platform)
    print(f"\n[lulu-dev-workflow init] {platform} hook registered: {hook_command}")

    hook_path, hook_created = ensure_hook_config(project_root, platform=platform)
    if hook_created:
        print(f"\n[lulu-dev-workflow init] Created hook-config: {hook_path}")

    print("\n[lulu-dev-workflow init] All sub-workflows initialized successfully.")
    return 0
