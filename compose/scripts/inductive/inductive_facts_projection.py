#!/usr/bin/env python3
"""K2 inductive projection — RETIRED (K4 fact-native).

Facts are written directly by the discovery loop (seed / settle-open).
Do not project decisions[] → _facts.json.

Design: docs/domain/archive/compose/archive-2.0/compose-fact-first-k4-fact-native-design.md §6 / §11 Phase 2.
"""

from __future__ import annotations

import argparse
import sys

RETIRED_MSG = (
    "inductive facts projection is retired (K4): "
    "facts are written by the discovery loop (seed/settle); do not project"
)


def cmd_project(_args: argparse.Namespace) -> int:
    print(f"错误：{RETIRED_MSG}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    project_p = sub.add_parser(
        "project",
        help="RETIRED — facts are written by inductive seed/settle",
    )
    project_p.add_argument("--revision-dir", type=str, required=True)
    project_p.add_argument("--inductive-dir", type=str, default=None)
    project_p.add_argument("--profile", type=str, required=True)
    project_p.add_argument("--project-root", type=str, default=".")
    project_p.set_defaults(func=cmd_project)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
