#!/usr/bin/env python3
"""Workflow-config CLI for lulu-dev-workflow.

Subcommands:
    get-model       Resolve subagent model for a workflow stage (JSON stdout)
    configure       Download workflow-config.json to workflowConfig path
    resolve-path    Print resolved workflow-config.json path
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from fetch_template import FetchTemplateError  # noqa: E402
from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    default_configure_blob_url,
    resolve_subagent_model,
    resolve_workflow_config_path,
)

_CMD_GET_MODEL = "get-model"
_CMD_CONFIGURE = "configure"
_CMD_RESOLVE_PATH = "resolve-path"


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


def _cmd_get_model(args: argparse.Namespace) -> int:
    model = resolve_subagent_model(args.project_root, args.stage, args.platform)
    if model:
        print(json.dumps({"model": model}, ensure_ascii=False))
    else:
        print("{}")
    return 0


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


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow config utilities.")
    parent = argparse.ArgumentParser(add_help=False)
    _add_project_args(parent)
    sub = parser.add_subparsers(dest="command", required=True)

    get_model = sub.add_parser(
        _CMD_GET_MODEL,
        parents=[parent],
        help="Resolve subagent model for a workflow stage.",
    )
    get_model.add_argument("--stage", required=True, help="Workflow stage name (e.g. tech-code).")

    configure = sub.add_parser(
        _CMD_CONFIGURE,
        parents=[parent],
        help="Download workflow-config.json to workflowConfig path.",
    )
    configure.add_argument(
        "--url",
        default=default_configure_blob_url(),
        help="GitHub blob URL for workflow-config.json (default: framework template).",
    )

    sub.add_parser(
        _CMD_RESOLVE_PATH,
        parents=[parent],
        help="Print resolved workflow-config.json path.",
    )

    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()

    if args.command == _CMD_GET_MODEL:
        return _cmd_get_model(args)
    if args.command == _CMD_CONFIGURE:
        return _cmd_configure(args)
    if args.command == _CMD_RESOLVE_PATH:
        return _cmd_resolve_path(args)

    parser.print_help()
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    return _cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
