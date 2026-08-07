#!/usr/bin/env python3
"""Control for ``_topic-current.json`` (archive-10.0 T1).

Subcommands: status · set · set-conclusion · confirm-conclusion · clear

``set`` persists the current topic **after clarify** (human adopt already
done in dialogue). ``confirm-conclusion`` marks Topic Loop handoff ready
for fact-settle. No phase ordering on disk.

CLI: ``python3 topic_current_control.py --help``

Process how: docs/domain/archive/compose/archive-10.0/
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

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from topic_current_schema import (  # noqa: E402
    empty_topic_current,
    load_topic_current,
    save_topic_current,
    topic_current_path,
)


def _slice(revision_dir: str) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    path = topic_current_path(_slice(args.revision_dir))
    data = load_topic_current(path)
    return _ok({"ok": True, "path": str(path), "topic": data})


def cmd_set(args: argparse.Namespace) -> int:
    title = str(args.title or "").strip()
    scope = str(args.scope or "").strip()
    if not title or not scope:
        return _fail("set requires non-empty --title and --scope")
    path = topic_current_path(_slice(args.revision_dir))
    data = {
        "version": "1",
        "title": title,
        "scope": scope,
        "clarified": True,
        "conclusion": None,
        "conclusion_confirmed": False,
    }
    try:
        saved = save_topic_current(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "path": str(path), "topic": saved})


def cmd_set_conclusion(args: argparse.Namespace) -> int:
    text = str(args.text or "").strip()
    if not text:
        return _fail("set-conclusion requires non-empty --text")
    path = topic_current_path(_slice(args.revision_dir))
    data = load_topic_current(path)
    if not data.get("clarified"):
        return _fail("set-conclusion requires a clarified topic (run set first)")
    data["conclusion"] = text
    data["conclusion_confirmed"] = False
    try:
        saved = save_topic_current(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "path": str(path), "topic": saved})


def cmd_confirm_conclusion(args: argparse.Namespace) -> int:
    path = topic_current_path(_slice(args.revision_dir))
    data = load_topic_current(path)
    if not data.get("clarified"):
        return _fail("confirm-conclusion requires a clarified topic")
    if not (isinstance(data.get("conclusion"), str) and data["conclusion"].strip()):
        return _fail("confirm-conclusion requires set-conclusion first")
    data["conclusion_confirmed"] = True
    try:
        saved = save_topic_current(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "path": str(path), "topic": saved})


def cmd_clear(args: argparse.Namespace) -> int:
    path = topic_current_path(_slice(args.revision_dir))
    saved = save_topic_current(path, empty_topic_current())
    return _ok({"ok": True, "path": str(path), "topic": saved})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("set", help="Persist current topic after clarify")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--scope", required=True)
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("set-conclusion")
    p.add_argument("--revision-dir", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_set_conclusion)

    p = sub.add_parser("confirm-conclusion")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_confirm_conclusion)

    p = sub.add_parser("clear")
    p.add_argument("--revision-dir", required=True)
    p.set_defaults(func=cmd_clear)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
