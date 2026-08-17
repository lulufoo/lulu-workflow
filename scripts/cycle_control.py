#!/usr/bin/env python3
"""Cycle control for lulu-dev-workflow orchestrator.

Subcommands:
    init-project          Project-level init (sub-workflows + hooks)
    configure             Download workflow-config.json to workflowConfig path
    resolve-config-path   Print resolved workflow-config.json path
    start                 Create a new cycle container; stdout last line: cycle_id
    archive               Prune old cycle dirs, keeping N most recent
    menu                  Feature Resolution menu (T#/F# rows + N/M)
    resolve-token         Resolve menu token T#/F# to cycle_id
    bind-context          Bind conversation → cycle/stage in active-context
    info                  JSON metadata for one cycle (--cycle-id)
    validate              Exit 0 when cycle exists in index and on disk
    topic-digest          Topic association candidates for New feature (JSON)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from active_context_schema import resolve_conversation_id, write_entry  # noqa: E402
from fetch_template import FetchTemplateError  # noqa: E402
from cycle_schema import (  # noqa: E402
    append_cycle,
    build_cycle_info,
    build_topic_digest,
    cycle_exists,
    cycle_type_from_id,
    ensure_container_dir,
    format_cycles_menu,
    generate_cycle_id,
    prune_cycles,
    resolve_cache_dir,
    resolve_menu_token,
    validate_cycle,
)
from init_ops import run_init_project  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from transition_table import allowed_stages  # noqa: E402
from workflow_config_schema import (  # noqa: E402
    apply_workflow_config_from_url,
    resolve_workflow_config_path,
)

_CMD_INIT_PROJECT = "init-project"
_CMD_CONFIGURE = "configure"
_CMD_RESOLVE_CONFIG_PATH = "resolve-config-path"
_CMD_START = "start"
_CMD_ARCHIVE = "archive"
_CMD_MENU = "menu"
_CMD_RESOLVE_TOKEN = "resolve-token"
_CMD_BIND_CONTEXT = "bind-context"
_CMD_INFO = "info"
_CMD_VALIDATE = "validate"
_CMD_TOPIC_DIGEST = "topic-digest"


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
        choices=["cursor", "copilot", "claude"],
        help="Platform override (default: auto-detect).",
    )


def cmd_init_project(args: argparse.Namespace) -> int:
    platform = args.platform or detect_platform(strict=False)
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
    append_cycle(cache_dir, cycle_id, name, topic_id=topic_id)
    return cycle_id


def cmd_start(args: argparse.Namespace) -> int:
    cycle_id = start_cycle(
        args.project_root,
        name=args.name,
        cycle_type=args.cycle_type,
        topic_id=args.topic_id,
        platform=args.platform,
    )
    print(cycle_id)
    return 0


def cmd_menu(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    print(format_cycles_menu(cache_dir))
    return 0


def cmd_resolve_token(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    cycle_id = resolve_menu_token(cache_dir, args.token)
    if cycle_id is None:
        print(f"Error: invalid or out-of-range token: {args.token!r}", file=sys.stderr)
        return 1
    print(cycle_id)
    return 0


def cmd_bind_context(args: argparse.Namespace) -> int:
    conversation_id = resolve_conversation_id(args.conversation_id)
    if not conversation_id:
        print(
            "Error: --conversation-id is required (or LULU_CONVERSATION_ID)",
            file=sys.stderr,
        )
        return 1

    skill_dir_raw = (args.skill_dir or "").strip()
    if not skill_dir_raw:
        print("Error: --skill-dir must be non-empty", file=sys.stderr)
        return 1
    stage = Path(skill_dir_raw.rstrip("/")).name
    if not stage or stage in (".", ".."):
        print(
            f"Error: cannot derive stage from --skill-dir: {args.skill_dir!r}",
            file=sys.stderr,
        )
        return 1

    platform = args.platform or detect_platform(strict=False)
    cache_dir = resolve_cache_dir(args.project_root, platform)
    ok, message = validate_cycle(cache_dir, args.cycle_id)
    if not ok:
        print(f"Error: {message}", file=sys.stderr)
        return 1

    cycle_type = cycle_type_from_id(args.cycle_id)
    if stage not in allowed_stages(cycle_type):
        print(
            f"Error: stage {stage!r} not allowed for cycle_type {cycle_type!r}",
            file=sys.stderr,
        )
        return 1

    try:
        write_entry(
            args.project_root,
            platform,
            conversation_id,
            args.cycle_id,
            stage,
            cycle_type=cycle_type,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
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


def cmd_archive(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    prune_cycles(cache_dir, args.keep, args.project_root)
    return 0


def cmd_topic_digest(args: argparse.Namespace) -> int:
    cache_dir = resolve_cache_dir(args.project_root, args.platform)
    payload = build_topic_digest(cache_dir, args.stage)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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
        required=True,
        help="Local workflow-config.json path or explicit GitHub blob URL.",
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

    menu_cmd = sub.add_parser(
        _CMD_MENU,
        help="Print Feature Resolution menu (T#/F# rows + N/M).",
    )
    menu_cmd.set_defaults(handler=cmd_menu)

    resolve_token = sub.add_parser(
        _CMD_RESOLVE_TOKEN,
        help="Resolve menu token T#/F# to cycle_id.",
    )
    resolve_token.add_argument(
        "--token",
        required=True,
        help="Menu token (e.g. T1, F2).",
    )
    resolve_token.set_defaults(handler=cmd_resolve_token)

    bind_context = sub.add_parser(
        _CMD_BIND_CONTEXT,
        help="Bind conversation to cycle/stage in active-context.",
    )
    bind_context.add_argument("--cycle-id", required=True, help="Cycle ID to bind.")
    bind_context.add_argument(
        "--skill-dir",
        required=True,
        help="Active sub-SKILL directory; basename becomes stage.",
    )
    bind_context.add_argument(
        "--conversation-id",
        default=None,
        help="Conversation ID for active-context indexing (hook may inject).",
    )
    bind_context.set_defaults(handler=cmd_bind_context)

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

    topic_digest = sub.add_parser(
        _CMD_TOPIC_DIGEST,
        help="Emit topic association candidates (JSON) for New feature.",
    )
    topic_digest.add_argument(
        "--stage",
        required=True,
        help="Current sub-SKILL stage name (e.g. lulu-approach).",
    )
    topic_digest.set_defaults(handler=cmd_topic_digest)

    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()

    if args.command == _CMD_ARCHIVE and args.keep < 1:
        parser.error("archive --keep must be at least 1")

    return args.handler(args)


def main(argv: Optional[list[str]] = None) -> int:
    return _cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
