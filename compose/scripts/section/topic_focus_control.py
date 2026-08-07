#!/usr/bin/env python3
"""Control for ``_topic-focus.json`` (archive-9.0 T2/T3).

Subcommands: status · set · clear · set-phase

CLI: ``python3 topic_focus_control.py --help``

Process how: docs/domain/archive/compose/archive-9.0/
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
from narrative_arc_draft_schema import (  # noqa: E402
    load_narrative_arc_draft,
    narrative_arc_draft_path,
)
from topic_focus_schema import (  # noqa: E402
    empty_topic_focus,
    load_topic_focus,
    save_topic_focus,
    topic_focus_path,
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
    path = topic_focus_path(_slice(args.revision_dir))
    data = load_topic_focus(path)
    return _ok({"ok": True, "path": str(path), **data})


def cmd_set(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    draft_path = narrative_arc_draft_path(slice_dir)
    try:
        draft = load_narrative_arc_draft(draft_path)
    except ValueError as exc:
        return _fail(str(exc))
    leaf_ids = {leaf["id"] for leaf in draft["leaves"]}
    leaf_id = args.leaf_id.strip()
    if leaf_id not in leaf_ids:
        return _fail(f"leaf not in draft: {leaf_id!r}")
    phase = args.phase or "define"
    saved = save_topic_focus(
        topic_focus_path(slice_dir),
        {"version": "1", "focus": leaf_id, "phase": phase},
    )
    return _ok({"ok": True, **saved})


def cmd_clear(args: argparse.Namespace) -> int:
    saved = save_topic_focus(topic_focus_path(_slice(args.revision_dir)), empty_topic_focus())
    return _ok({"ok": True, **saved})


def cmd_set_phase(args: argparse.Namespace) -> int:
    path = topic_focus_path(_slice(args.revision_dir))
    data = load_topic_focus(path)
    if data.get("focus") is None:
        return _fail("cannot set phase without focus")
    phase = args.phase.strip()
    if phase not in {"define", "discuss", "summarize"}:
        return _fail("phase must be define|discuss|summarize")
    data["phase"] = phase
    saved = save_topic_focus(path, data)
    return _ok({"ok": True, **saved})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)

    p = sub.add_parser("status")
    add_rev(p)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("set")
    add_rev(p)
    p.add_argument("--leaf-id", required=True)
    p.add_argument("--phase", default="define")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("clear")
    add_rev(p)
    p.set_defaults(func=cmd_clear)

    p = sub.add_parser("set-phase")
    add_rev(p)
    p.add_argument("--phase", required=True)
    p.set_defaults(func=cmd_set_phase)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
