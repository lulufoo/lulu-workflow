#!/usr/bin/env python3
"""Fetch compose framework templates by scheme role and profile mapping."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_paths import (  # noqa: E402
    WORKFLOW_SCRIPTS,
    resolve_cycle_id,
    resolve_profile_id,
)

if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from compose_template_registry import (  # noqa: E402
    ComposeTemplateError,
    framework_section,
    resolve_config_key,
    scheme_template_keys,
)
from fetch_template import FetchTemplateError, fetch_template  # noqa: E402


class FetchComposeFrameworkError(Exception):
    """Raised when role resolution or template fetch fails."""


def fetch_compose_framework(
    role: str,
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    platform: Optional[str] = None,
    force: bool = False,
) -> str:
    pid = str(profile_id or "").strip()
    if not pid:
        raise FetchComposeFrameworkError("profile_id required")
    root = project_root.resolve()
    try:
        section = framework_section(
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
        )
        config_key = resolve_config_key(
            role,
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
        )
        return fetch_template(
            section=section,
            key=config_key,
            project_root=root,
            platform=platform,
            force=force,
        )
    except (ComposeTemplateError, FetchTemplateError) as exc:
        raise FetchComposeFrameworkError(str(exc)) from exc


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch compose framework template by scheme role (markdown or JSON)",
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(scheme_template_keys()),
        help="Compose template scheme key",
    )
    parser.add_argument(
        "--cycle-id",
        default="",
        help="Cycle ID for session profile pointer (fallback: env / active-context)",
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Conversation ID for active-context cycle fallback",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--platform",
        choices=["cursor", "copilot"],
        help="Platform cache namespace (default: auto-detect)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass cache and re-fetch from GitHub",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip() or None
    try:
        cycle_id = resolve_cycle_id(
            project_root,
            cycle_id=cycle_id,
            conversation_id=args.conversation_id.strip() or None,
        )
        profile_id = resolve_profile_id(
            project_root=project_root,
            cycle_id=cycle_id,
        )
        content = fetch_compose_framework(
            role=args.role,
            project_root=project_root,
            profile_id=profile_id,
            cycle_id=cycle_id,
            conversation_id=args.conversation_id.strip() or None,
            platform=args.platform,
            force=args.force,
        )
    except (FetchComposeFrameworkError, ValueError, FileNotFoundError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
