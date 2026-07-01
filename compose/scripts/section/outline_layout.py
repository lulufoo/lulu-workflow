#!/usr/bin/env python3
"""Resolve outline block layout for a section key (initializing-runner I2g gate).

Subcommands:
    resolve    JSON layout for one intent key (block_key, last_in_block, block_intents, …)

CLI details: ``python3 outline_layout.py --help``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_doc_control import _load_outline, build_outline_intent_layout  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402


def resolve_layout_for_section(
    outline: dict[str, Any],
    section_key: str,
) -> dict[str, Any]:
    """Return layout metadata plus block_intents for one intent key."""
    key = section_key.strip().upper()
    layout_map = build_outline_intent_layout(outline)
    if key not in layout_map:
        raise ValueError(f"section {key!r} not found in outline-registry intents")

    layout = layout_map[key]
    block_key = str(layout["block_key"]).upper()
    block = (outline.get("blocks") or {}).get(block_key) or {}
    block_intents = [str(item).upper() for item in block.get("intents") or []]
    return {
        "section_key": key,
        "block_key": block_key,
        "block_heading": layout["block_heading"],
        "block_index": layout["block_index"],
        "first_in_block": layout["first_in_block"],
        "last_in_block": layout["last_in_block"],
        "last_block": layout["last_block"],
        "block_intents": block_intents,
    }


def cmd_resolve(args: argparse.Namespace) -> int:
    profile_id = (args.profile or DEFAULT_COMPOSE_PROFILE_ID).strip() or DEFAULT_COMPOSE_PROFILE_ID
    try:
        outline = _load_outline(
            outline_path=args.outline_path.resolve() if args.outline_path else None,
            project_root=args.project_root.resolve(),
            profile_id=profile_id,
        )
        payload = resolve_layout_for_section(outline, args.section)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_parser = sub.add_parser("resolve", help="Resolve outline layout for one section key")
    resolve_parser.add_argument("--section", type=str, required=True)
    resolve_parser.add_argument("--outline-path", type=Path, default=None)
    resolve_parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    resolve_parser.add_argument("--project-root", type=Path, default=Path("."))
    resolve_parser.set_defaults(func=cmd_resolve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
