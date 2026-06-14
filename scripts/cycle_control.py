#!/usr/bin/env python3
"""Cycle control for lulu-dev-workflow orchestrator.

Subcommands:
    init-project          Project-level init (sub-workflows + hooks)
    configure             Download workflow-config.json to workflowConfig path
    resolve-config-path   Print resolved workflow-config.json path
    start                 Create a new cycle container; stdout last line: cycle_id
    archive               Prune old cycle dirs, keeping N most recent
    list                  Print cycles.json summary for Feature Resolution
    info                  JSON metadata for one cycle (--cycle-id)
    validate              Exit 0 when cycle exists in index and on disk
    set-execution-mode    Update execution_mode for one cycle in cycles.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from fetch_template import FetchTemplateError  # noqa: E402
from cycle_schema import (  # noqa: E402
    append_cycle,
    build_cycle_info,
    cycle_exists,
    ensure_container_dir,
    format_cycles_list,
    generate_cycle_id,
    prune_cycles,
    resolve_cache_dir,
    set_execution_mode,
    validate_cycle,
)
from init_ops import run_init_project  # noqa: E402
from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    default_configure_blob_url,
    resolve_workflow_config_path,
)

_CMD_INIT_PROJECT = "init-project"
_CMD_CONFIGURE = "configure"
_CMD_RESOLVE_CONFIG_PATH = "resolve-config-path"
_CMD_START = "start"
_CMD_ARCHIVE = "archive"
_CMD_LIST = "list"
_CMD_INFO = "info"
_CMD_VALIDATE = "validate"
_CMD_SET_EXECUTION_MODE = "set-execution-mode"


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


def cmd_init_project(args: argparse.Namespace) -> int:
    platform = args.platform or "cursor"
    return run_init_project(args.project_root, platform)


def cmd_configure(args: argparse.Namespace) -> int:
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


def cmd_resolve_config_path(args: argparse.Namespace) -> int:
    path = resolve_workflow_config_path(args.project_root, args.platform)
    print(path.as_posix())
    return 0


def start_cycle(
    project_root: Path,
    *,
    name: str,
    cycle_type: str = "feature",
    mode: str = "guided",
    topic_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> str:
    if not project_root.is_dir():
        print(f"Error: --project-root does not exist: {project_root}", file=sys.stderr)
        raise SystemExit(1)

    cache_dir = resolve_cache_dir(project_root, platform)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if (
        cycle_type == "feature"
        and topic_id is not None
        and not cycle_exists(cache_dir, topic_id)
    ):
        print(f"Error: topic_id not found in cycles.json: {topic_id}", file=sys.stderr)
        raise SystemExit(1)

    cycle_id = generate_cycle_id(cycle_type)
    ensure_container_dir(cache_dir, cycle_id)
    append_cycle(cache_dir, cycle_id, name, mode, topic_id=topic_id)
    return cycle_id


def cmd_start(args: argparse.Namespace) -> int:
    cycle_id = start_cycle(
        args.project_root,
        name=args.name,
        cycle_type=args.cycle_type,
        mode=args.mode,
        topic_id=args.topic_id,
        platform=args.platform,
    )
    print(cycle_id)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    print(format_cycles_list(cache_dir))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    info = build_cycle_info(cache_dir, args.cycle_id)
    if info is None:
        print(f"Error: cycle-id not found: {args.cycle_id}", file=sys.stderr)
        return 1
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    ok, message = validate_cycle(cache_dir, args.cycle_id)
    if not ok:
        print(f"Error: {message}", file=sys.stderr)
        return 1
    return 0


def cmd_set_execution_mode(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    try:
        payload = set_execution_mode(cache_dir, args.cycle_id, args.mode)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "command": _CMD_SET_EXECUTION_MODE,
                    "current_state": args.cycle_id,
                    "message": f"{exc}. Pause execution and wait for user direction.",
                },
                separators=(",", ":"),
            )
        )
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(payload, separators=(",", ":")))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    prune_cycles(cache_dir, args.keep, args.project_root)
    return 0


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="lulu-dev-workflow cycle control.")
    _add_project_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    init_project = sub.add_parser(
        _CMD_INIT_PROJECT,
        help="Initialize lulu-dev-workflow in a project (all sub-workflows).",
    )
    init_project.set_defaults(handler=cmd_init_project)

    configure = sub.add_parser(
        _CMD_CONFIGURE,
        help="Download workflow-config.json to workflowConfig path.",
    )
    configure.add_argument(
        "--url",
        default=default_configure_blob_url(),
        help="GitHub blob URL for workflow-config.json (default: framework template).",
    )
    configure.set_defaults(handler=cmd_configure)

    resolve_path = sub.add_parser(
        _CMD_RESOLVE_CONFIG_PATH,
        help="Print resolved workflow-config.json path.",
    )
    resolve_path.set_defaults(handler=cmd_resolve_config_path)

    start = sub.add_parser(
        _CMD_START,
        help="Create a new cycle container.",
    )
    start.add_argument("--name", required=True, help="Human-readable name.")
    start.add_argument(
        "--type",
        choices=["topic", "feature"],
        default="feature",
        dest="cycle_type",
        help="Container type (default: feature).",
    )
    start.add_argument(
        "--mode",
        choices=["guided", "autonomous"],
        default="guided",
        help="Execution mode (default: guided).",
    )
    start.add_argument(
        "--topic-id",
        default=None,
        help="Associate feature with an existing topic (feature type only).",
    )
    start.set_defaults(handler=cmd_start)

    archive = sub.add_parser(
        _CMD_ARCHIVE,
        help="Prune old cycle directories.",
    )
    archive.add_argument(
        "--keep",
        type=int,
        default=5,
        metavar="N",
        help="Number of most-recent cycles to keep (default: 5).",
    )
    archive.set_defaults(handler=cmd_archive)

    list_cmd = sub.add_parser(
        _CMD_LIST,
        help="Print cycles.json summary for Feature Resolution.",
    )
    list_cmd.set_defaults(handler=cmd_list)

    info = sub.add_parser(
        _CMD_INFO,
        help="Print JSON metadata for one cycle.",
    )
    info.add_argument("--cycle-id", required=True, help="Cycle ID to inspect.")
    info.set_defaults(handler=cmd_info)

    validate = sub.add_parser(
        _CMD_VALIDATE,
        help="Verify cycle exists in cycles.json and on disk.",
    )
    validate.add_argument("--cycle-id", required=True, help="Cycle ID to validate.")
    validate.set_defaults(handler=cmd_validate)

    set_mode = sub.add_parser(
        _CMD_SET_EXECUTION_MODE,
        help="Update execution_mode for one cycle in cycles.json.",
    )
    set_mode.add_argument("--cycle-id", required=True, help="Cycle ID to update.")
    set_mode.add_argument(
        "--mode",
        required=True,
        choices=sorted({"guided", "autonomous"}),
        help="New execution mode.",
    )
    set_mode.set_defaults(handler=cmd_set_execution_mode)

    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()

    if args.command == _CMD_ARCHIVE and args.keep < 1:
        parser.error("archive --keep must be at least 1")

    return args.handler(args)


def main(argv: Optional[list[str]] = None) -> int:
    return _cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
