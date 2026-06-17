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

from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, WORKFLOW_SCRIPTS  # noqa: E402

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
    platform: Optional[str] = None,
    force: bool = False,
) -> str:
    pid = profile_id or DEFAULT_COMPOSE_PROFILE_ID
    try:
        section = framework_section(pid)
        config_key = resolve_config_key(role, pid)
        return fetch_template(
            section=section,
            key=config_key,
            project_root=project_root,
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
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile id (default: tech-plan)",
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

    try:
        content = fetch_compose_framework(
            role=args.role,
            project_root=Path(args.project_root).resolve(),
            profile_id=args.profile.strip(),
            platform=args.platform,
            force=args.force,
        )
    except FetchComposeFrameworkError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
