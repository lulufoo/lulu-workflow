#!/usr/bin/env python3
"""Control for ``_narrative-arc.draft.json`` (archive-9.0).

Subcommands: validate · write · show · add-node · move · rename · deepen ·
attach-fact · ensure-skeleton

CLI: ``python3 narrative_arc_draft_control.py --help``

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
from facts_schema import facts_path, load_facts  # noqa: E402
from narrative_arc_draft_schema import (  # noqa: E402
    add_leaf_node,
    attach_fact,
    deepen_leaf,
    empty_draft,
    load_narrative_arc_draft,
    move_node,
    narrative_arc_draft_path,
    rename_leaf,
    save_narrative_arc_draft,
    validate_narrative_arc_draft,
)
from topic_focus_schema import (  # noqa: E402
    empty_topic_focus,
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


def cmd_validate(args: argparse.Namespace) -> int:
    path = narrative_arc_draft_path(_slice(args.revision_dir))
    if not path.is_file():
        return _fail(f"draft not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")
    errors = validate_narrative_arc_draft(data)
    if errors:
        return _fail("; ".join(errors))
    return _ok({"ok": True, "path": str(path), "status": "draft"})


def cmd_write(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    path = narrative_arc_draft_path(slice_dir)
    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")
    try:
        saved = save_narrative_arc_draft(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    focus_p = topic_focus_path(slice_dir)
    if not focus_p.is_file():
        save_topic_focus(focus_p, empty_topic_focus())
    return _ok({"ok": True, "path": str(path), "leaf_count": len(saved["leaves"])})


def cmd_show(args: argparse.Namespace) -> int:
    path = narrative_arc_draft_path(_slice(args.revision_dir))
    try:
        data = load_narrative_arc_draft(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(data)


def cmd_ensure_skeleton(args: argparse.Namespace) -> int:
    """Create a minimal draft from current facts (one leaf per lens bucket)."""
    slice_dir = _slice(args.revision_dir)
    path = narrative_arc_draft_path(slice_dir)
    if path.is_file() and not args.force:
        return _ok({"ok": True, "path": str(path), "created": False})
    fpath = facts_path(slice_dir)
    facts = load_facts(fpath) if fpath.is_file() else []
    draft = empty_draft(source="post-g1-auto")
    by_lens: dict[str, list[str]] = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        fid = str(fact.get("id", "")).strip()
        if not fid:
            continue
        tags = [str(t).strip().upper() for t in (fact.get("lens_tags") or []) if str(t).strip()]
        key = tags[0] if tags else "UNTAGGED"
        by_lens.setdefault(key, []).append(fid)
    children = []
    leaves = []
    mounts: dict[str, str] = {}
    if not by_lens:
        lid = "leaf-seed"
        children.append({"id": lid, "title": "Seed shape", "children": []})
        leaves.append({"id": lid, "title": "Seed shape", "fact_ids": []})
        mounts[lid] = "seed"
    else:
        for i, (lens, fids) in enumerate(sorted(by_lens.items()), start=1):
            lid = f"leaf-{lens.lower()}-{i}"
            title = f"{lens} cluster"
            children.append({"id": lid, "title": title, "children": []})
            leaves.append({"id": lid, "title": title, "fact_ids": fids})
            mounts[lid] = "seed"
    draft["tree"] = {
        "id": "root",
        "title": "Narrative axis",
        "children": [{"id": "group-seed", "title": "Seed", "children": children}],
    }
    draft["leaves"] = leaves
    draft["meta"]["leaf_mounts"] = mounts
    try:
        saved = save_narrative_arc_draft(path, draft)
    except ValueError as exc:
        return _fail(str(exc))
    save_topic_focus(topic_focus_path(slice_dir), empty_topic_focus())
    return _ok(
        {
            "ok": True,
            "path": str(path),
            "created": True,
            "leaf_count": len(saved["leaves"]),
        }
    )


def _load(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    slice_dir = _slice(args.revision_dir)
    path = narrative_arc_draft_path(slice_dir)
    return path, load_narrative_arc_draft(path)


def cmd_add_node(args: argparse.Namespace) -> int:
    path, data = _load(args)
    index = None if args.index is None else int(args.index)
    try:
        updated = add_leaf_node(
            data,
            parent_id=args.parent_id,
            leaf_id=args.leaf_id,
            title=args.title,
            index=index,
        )
        save_narrative_arc_draft(path, updated)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "leaf_id": args.leaf_id, "path": str(path)})


def cmd_move(args: argparse.Namespace) -> int:
    path, data = _load(args)
    index = None if args.index is None else int(args.index)
    try:
        updated = move_node(
            data,
            node_id=args.node_id,
            new_parent=args.new_parent,
            index=index,
        )
        save_narrative_arc_draft(path, updated)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "node_id": args.node_id, "path": str(path)})


def cmd_rename(args: argparse.Namespace) -> int:
    path, data = _load(args)
    try:
        updated = rename_leaf(data, leaf_id=args.leaf_id, title=args.title)
        save_narrative_arc_draft(path, updated)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "leaf_id": args.leaf_id, "title": args.title})


def cmd_deepen(args: argparse.Namespace) -> int:
    path, data = _load(args)
    try:
        updated = deepen_leaf(data, leaf_id=args.leaf_id, note=args.note or None)
        save_narrative_arc_draft(path, updated)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "leaf_id": args.leaf_id})


def cmd_attach_fact(args: argparse.Namespace) -> int:
    slice_dir = _slice(args.revision_dir)
    from topic_focus_schema import load_topic_focus

    focus = load_topic_focus(topic_focus_path(slice_dir))
    leaf_id = args.leaf_id or focus.get("focus")
    if not leaf_id:
        return _fail("attach-fact requires focus or --leaf-id")
    fpath = facts_path(slice_dir)
    if not fpath.is_file():
        return _fail(f"facts not found: {fpath}")
    facts = load_facts(fpath)
    if not any(str(f.get("id", "")).strip() == args.fact_id for f in facts):
        return _fail(f"fact not in _facts.json: {args.fact_id!r}")
    path = narrative_arc_draft_path(slice_dir)
    try:
        data = load_narrative_arc_draft(path)
        updated = attach_fact(data, leaf_id=str(leaf_id), fact_id=args.fact_id)
        save_narrative_arc_draft(path, updated)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "leaf_id": leaf_id, "fact_id": args.fact_id})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_rev(p: argparse.ArgumentParser) -> None:
        p.add_argument("--revision-dir", required=True)

    p = sub.add_parser("validate")
    add_rev(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("write")
    add_rev(p)
    p.add_argument("--file", default="")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("show")
    add_rev(p)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("ensure-skeleton")
    add_rev(p)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_ensure_skeleton)

    p = sub.add_parser("add-node")
    add_rev(p)
    p.add_argument("--parent-id", required=True)
    p.add_argument("--leaf-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--index", type=int, default=None)
    p.set_defaults(func=cmd_add_node)

    p = sub.add_parser("move")
    add_rev(p)
    p.add_argument("--node-id", required=True)
    p.add_argument("--new-parent", required=True)
    p.add_argument("--index", type=int, default=None)
    p.set_defaults(func=cmd_move)

    p = sub.add_parser("rename")
    add_rev(p)
    p.add_argument("--leaf-id", required=True)
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("deepen")
    add_rev(p)
    p.add_argument("--leaf-id", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_deepen)

    p = sub.add_parser("attach-fact")
    add_rev(p)
    p.add_argument("--fact-id", required=True)
    p.add_argument("--leaf-id", default="")
    p.set_defaults(func=cmd_attach_fact)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
