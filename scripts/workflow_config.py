#!/usr/bin/env python3
"""Workflow-config CLI for lulu-workflow.

Subcommands:
    configure           Download workflow-config and write stages/ layout
    resolve-path        Print resolved $WORKFLOW_DIR config root
    resolve-stage-path  Print resolved stages/{stage}.json path
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from fetch_template import FetchTemplateError  # noqa: E402
from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    resolve_stage_config_path,
    resolve_workflow_config_path,
)

_CMD_CONFIGURE = "configure"
_CMD_RESOLVE_PATH = "resolve-path"
_CMD_RESOLVE_STAGE_PATH = "resolve-stage-path"


def _add_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Project root directory.",
    )
    parser.add_argument(
        "--platform",
        default=None,
        choices=["cursor", "copilot"],
        help="Platform override (default: auto-detect).",
    )


def _cmd_configure(args: argparse.Namespace) -> int:
    try:
        target = apply_workflow_config_from_url(
            args.project_root,
            args.url,
            platform=args.platform,
        )
    except (FetchTemplateError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(target.as_posix())
    return 0


def _cmd_resolve_path(args: argparse.Namespace) -> int:
    path = resolve_workflow_config_path(args.project_root, args.platform)
    print(path.as_posix())
    return 0


def _cmd_resolve_stage_path(args: argparse.Namespace) -> int:
    path = resolve_stage_config_path(args.project_root, args.stage, args.platform)
    print(path.as_posix())
    return 0


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow config utilities.")
    parent = argparse.ArgumentParser(add_help=False)
    _add_project_args(parent)
    sub = parser.add_subparsers(dest="command", required=True)

    configure = sub.add_parser(
        _CMD_CONFIGURE,
        parents=[parent],
        help="Download workflow-config and write stages/ layout.",
    )
    configure.add_argument(
        "--url",
        required=True,
        help="Local workflow-config.json path or explicit GitHub blob URL.",
    )

    sub.add_parser(
        _CMD_RESOLVE_PATH,
        parents=[parent],
        help="Print resolved $WORKFLOW_DIR config root.",
    )

    resolve_stage = sub.add_parser(
        _CMD_RESOLVE_STAGE_PATH,
        parents=[parent],
        help="Print resolved stages/{stage}.json path.",
    )
    resolve_stage.add_argument("--stage", required=True, help="Workflow stage name.")

    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()

    if args.command == _CMD_CONFIGURE:
        return _cmd_configure(args)
    if args.command == _CMD_RESOLVE_PATH:
        return _cmd_resolve_path(args)
    if args.command == _CMD_RESOLVE_STAGE_PATH:
        return _cmd_resolve_stage_path(args)

    parser.print_help()
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    return _cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
