#!/usr/bin/env python3
"""Multi-subdesign slice helpers: root-facts migration gate + lock-tree.

Subcommands:
    check-root-facts     Fail if revision root still has ``_facts.json``
    migrate-root-facts   Move root ``_facts.json`` → ``L1/_facts.json`` (--confirm)
    lock-tree            Persist locked dependency tree + pointer + Lx dirs
    assemble-index       Build ``design-index.md`` when all production done
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
_SESSION = _SCRIPTS / "schema" / "session"
_SECTION = _SCRIPTS / "section"
for _p in (_HERE, _SESSION, _SECTION, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dependency_tree_schema import (  # noqa: E402
    DEPENDENCY_TREE_FILENAME,
    dependency_tree_path,
    load_dependency_tree,
    save_dependency_tree,
    validate_dependency_tree,
)
from discussion_pointer_schema import (  # noqa: E402
    build_pointer_from_tree,
    discussion_pointer_path,
    load_discussion_pointer,
    save_discussion_pointer,
)
from facts_schema import FACTS_BASENAME  # noqa: E402

DESIGN_INDEX_FILENAME = "design-index.md"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def root_facts_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / FACTS_BASENAME


def cmd_check_root_facts(revision_dir: Path) -> int:
    root = root_facts_path(revision_dir)
    if root.is_file():
        return _emit_error(
            f"root {FACTS_BASENAME} present; migrate to L1/ or remove before Split "
            f"(path={root.as_posix()})"
        )
    _emit({"ok": True, "command": "check-root-facts", "root_facts": False})
    return 0


def cmd_migrate_root_facts(revision_dir: Path, *, confirm: bool) -> int:
    if not confirm:
        return _emit_error("human --confirm required")
    rev = Path(revision_dir).resolve()
    src = root_facts_path(rev)
    if not src.is_file():
        _emit(
            {
                "ok": True,
                "command": "migrate-root-facts",
                "noop": True,
                "reason": "no root _facts.json",
            }
        )
        return 0
    dest_dir = rev / "L1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / FACTS_BASENAME
    if dest.is_file():
        return _emit_error(f"refusing to overwrite existing {dest.as_posix()}")
    shutil.move(str(src), str(dest))
    _emit(
        {
            "ok": True,
            "command": "migrate-root-facts",
            "from": src.as_posix(),
            "to": dest.as_posix(),
        }
    )
    return 0


def cmd_lock_tree(
    revision_dir: Path,
    *,
    tree_json: str | None,
    tree_file: Path | None,
    confirm: bool,
) -> int:
    if not confirm:
        return _emit_error("human --confirm required")
    rev = Path(revision_dir).resolve()
    root = root_facts_path(rev)
    if root.is_file():
        return _emit_error(
            f"root {FACTS_BASENAME} present; migrate to L1/ or remove before Split "
            f"(path={root.as_posix()})"
        )

    try:
        if tree_file is not None:
            raw = tree_file.read_text(encoding="utf-8")
        elif tree_json is not None:
            raw = tree_json
        else:
            return _emit_error("provide --tree-json or --tree-file")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return _emit_error(f"cannot read tree JSON: {exc}")

    if isinstance(data, dict) and "nodes" in data:
        tree = dict(data)
        tree.setdefault("version", 1)
        tree["status"] = "locked"
    else:
        return _emit_error("tree JSON must be an object with nodes/edges/order")

    errors = validate_dependency_tree(tree)
    if errors:
        return _emit_error("; ".join(errors))

    existing = dependency_tree_path(rev)
    if existing.is_file():
        try:
            prev = load_dependency_tree(rev)
        except (ValueError, json.JSONDecodeError):
            prev = None
        if prev is not None and prev.get("status") == "locked":
            return _emit_error(
                "dependency tree already locked; unlock/re-split not allowed in MVP "
                "(start a new revision)"
            )

    try:
        save_dependency_tree(rev, tree)
        pointer = build_pointer_from_tree(tree)
        save_discussion_pointer(rev, pointer, tree=tree)
        for node in tree["nodes"]:
            (rev / str(node["id"])).mkdir(parents=True, exist_ok=True)
    except (ValueError, OSError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "command": "lock-tree",
            "tree_path": dependency_tree_path(rev).as_posix(),
            "pointer_path": discussion_pointer_path(rev).as_posix(),
            "order": list(tree["order"]),
            "pointer": pointer["pointer"],
        }
    )
    return 0


def cmd_assemble_index(revision_dir: Path, *, confirm: bool) -> int:
    if not confirm:
        return _emit_error("human --confirm required")
    rev = Path(revision_dir).resolve()
    try:
        tree = load_dependency_tree(rev)
        pointer = load_discussion_pointer(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    if pointer.get("phase") != "production":
        return _emit_error("assemble-index requires phase=production")
    incomplete = [
        nid
        for nid in tree["order"]
        if pointer["by_id"][nid]["production"] != "done"
    ]
    if incomplete:
        return _emit_error(
            "not all nodes production=done: " + ", ".join(incomplete)
        )

    titles = {n["id"]: n.get("title", "") for n in tree["nodes"]}
    lines = [
        "# Design Index",
        "",
        "Delivery entry for this multi-subdesign package.",
        "",
        "## Dependency tree",
        "",
        f"- File: `{DEPENDENCY_TREE_FILENAME}`",
        f"- Order: {', '.join(tree['order'])}",
        "",
        "## Sub-documents",
        "",
        "| L id | title | path |",
        "|------|-------|------|",
    ]
    for nid in tree["order"]:
        path = f"{nid}/design-doc.md"
        lines.append(f"| {nid} | {titles.get(nid, '')} | `{path}` |")
    lines.extend(
        [
            "",
            "## Delivery",
            "",
            "Marker entry points at this `design-index.md`. "
            "Sub-L docs are not delivered separately.",
            "",
        ]
    )
    out = rev / DESIGN_INDEX_FILENAME
    out.write_text("\n".join(lines), encoding="utf-8")
    _emit(
        {
            "ok": True,
            "command": "assemble-index",
            "path": out.as_posix(),
            "parts": [f"{nid}/design-doc.md" for nid in tree["order"]],
        }
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-subdesign slice control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--revision-dir", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-root-facts", help="Hard-reject if root _facts.json exists")

    p_mig = sub.add_parser("migrate-root-facts", help="Move root _facts.json to L1/")
    p_mig.add_argument("--confirm", action="store_true")

    p_lock = sub.add_parser("lock-tree", help="Lock dependency tree + init pointer + Lx/")
    p_lock.add_argument("--tree-json", default=None)
    p_lock.add_argument("--tree-file", type=Path, default=None)
    p_lock.add_argument("--confirm", action="store_true")

    p_idx = sub.add_parser(
        "assemble-index",
        help="Write design-index.md after all production done",
    )
    p_idx.add_argument("--confirm", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rev = args.revision_dir.resolve()
    if args.command == "check-root-facts":
        return cmd_check_root_facts(rev)
    if args.command == "migrate-root-facts":
        return cmd_migrate_root_facts(rev, confirm=bool(args.confirm))
    if args.command == "lock-tree":
        return cmd_lock_tree(
            rev,
            tree_json=args.tree_json,
            tree_file=args.tree_file,
            confirm=bool(args.confirm),
        )
    if args.command == "assemble-index":
        return cmd_assemble_index(rev, confirm=bool(args.confirm))
    return _emit_error(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
