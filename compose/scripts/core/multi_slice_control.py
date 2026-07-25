#!/usr/bin/env python3
"""Multi-subdesign slice helpers: root-facts migration, lock-tree+rulers, intake.

Subcommands:
    check-root-facts     Fail if revision root still has ``_facts.json``
    migrate-root-facts   Move root ``_facts.json`` → ``L1/_facts.json`` (--confirm)
    write-intake         Persist split-intake.json (draft or complete slots)
    complete-intake      Mark intake status=complete after slot validation (--confirm)
    lock-tree            Persist locked dependency tree + pointer + Lx dirs
                         (+ slice-rulers when multi-L)
    check-split-ready    Assert tree locked; multi-L requires locked rulers
    assemble-index       Build ``design-index.md`` when all production done

Design rationale (source repo, why-only):
docs/domain/archive/compose/archive-4.0/compose-multi-subdesign-split-runner-scheme.md
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
from slice_rulers_schema import (  # noqa: E402
    load_slice_rulers,
    save_slice_rulers,
    slice_rulers_path,
    validate_slice_rulers,
)
from split_intake_schema import (  # noqa: E402
    empty_intake,
    load_split_intake,
    save_split_intake,
    split_intake_path,
    validate_split_intake,
)

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


def _load_json_blob(
    *,
    raw_json: str | None,
    file_path: Path | None,
    label: str,
) -> dict[str, Any] | str:
    try:
        if file_path is not None:
            raw = file_path.read_text(encoding="utf-8")
        elif raw_json is not None:
            raw = raw_json
        else:
            return f"provide --{label}-json or --{label}-file"
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return f"cannot read {label} JSON: {exc}"
    if not isinstance(data, dict):
        return f"{label} JSON must be an object"
    return data


def cmd_write_intake(
    revision_dir: Path,
    *,
    intake_json: str | None,
    intake_file: Path | None,
) -> int:
    rev = Path(revision_dir).resolve()
    loaded = _load_json_blob(
        raw_json=intake_json, file_path=intake_file, label="intake"
    )
    if isinstance(loaded, str):
        return _emit_error(loaded)
    data = dict(loaded)
    data.setdefault("version", 1)
    if "slots" not in data:
        base = empty_intake()
        base["slots"].update(
            {k: str(v) for k, v in data.items() if k in base["slots"]}
        )
        data = base
    data["status"] = "draft"
    errors = validate_split_intake(data)
    if errors:
        return _emit_error("; ".join(errors))
    try:
        path = save_split_intake(rev, data)
    except ValueError as exc:
        return _emit_error(str(exc))
    _emit(
        {
            "ok": True,
            "command": "write-intake",
            "path": path.as_posix(),
            "status": data["status"],
        }
    )
    return 0


def cmd_complete_intake(revision_dir: Path, *, confirm: bool) -> int:
    if not confirm:
        return _emit_error("human --confirm required")
    rev = Path(revision_dir).resolve()
    try:
        data = load_split_intake(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(str(exc))
    data["status"] = "complete"
    errors = validate_split_intake(data)
    if errors:
        return _emit_error("; ".join(errors))
    try:
        path = save_split_intake(rev, data)
    except ValueError as exc:
        return _emit_error(str(exc))
    _emit(
        {
            "ok": True,
            "command": "complete-intake",
            "path": path.as_posix(),
            "status": "complete",
        }
    )
    return 0


def cmd_lock_tree(
    revision_dir: Path,
    *,
    tree_json: str | None,
    tree_file: Path | None,
    rulers_json: str | None,
    rulers_file: Path | None,
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

    loaded = _load_json_blob(raw_json=tree_json, file_path=tree_file, label="tree")
    if isinstance(loaded, str):
        return _emit_error(loaded)
    data = loaded

    if "nodes" not in data:
        return _emit_error("tree JSON must be an object with nodes/edges/order")
    tree = dict(data)
    tree.setdefault("version", 1)
    tree["status"] = "locked"

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

    node_ids = [str(n["id"]) for n in tree["nodes"]]
    multi = len(node_ids) >= 2
    rulers_payload: dict[str, Any] | None = None
    if multi:
        rloaded = _load_json_blob(
            raw_json=rulers_json, file_path=rulers_file, label="rulers"
        )
        if isinstance(rloaded, str):
            return _emit_error(
                f"multi-L lock requires slice rulers ({rloaded})"
            )
        rulers_payload = dict(rloaded)
        rulers_payload.setdefault("version", 1)
        rulers_payload["status"] = "locked"
        r_errors = validate_slice_rulers(
            rulers_payload, required_node_ids=node_ids
        )
        if r_errors:
            return _emit_error("; ".join(r_errors))
    elif rulers_json is not None or rulers_file is not None:
        # Single-L: optional rulers allowed if provided and valid for L1 only
        rloaded = _load_json_blob(
            raw_json=rulers_json, file_path=rulers_file, label="rulers"
        )
        if isinstance(rloaded, str):
            return _emit_error(rloaded)
        rulers_payload = dict(rloaded)
        rulers_payload.setdefault("version", 1)
        rulers_payload["status"] = "locked"
        r_errors = validate_slice_rulers(
            rulers_payload, required_node_ids=node_ids
        )
        if r_errors:
            return _emit_error("; ".join(r_errors))

    try:
        save_dependency_tree(rev, tree)
        pointer = build_pointer_from_tree(tree)
        save_discussion_pointer(rev, pointer, tree=tree)
        for node in tree["nodes"]:
            (rev / str(node["id"])).mkdir(parents=True, exist_ok=True)
        rulers_path_out: str | None = None
        if rulers_payload is not None:
            rpath = save_slice_rulers(rev, rulers_payload)
            rulers_path_out = rpath.as_posix()
        elif slice_rulers_path(rev).is_file():
            # Single-L exempt: leave any stray file untouched; do not require it
            pass
    except (ValueError, OSError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "command": "lock-tree",
            "tree_path": dependency_tree_path(rev).as_posix(),
            "pointer_path": discussion_pointer_path(rev).as_posix(),
            "rulers_path": rulers_path_out,
            "node_ids": list(tree["order"]),
            "focus": pointer["focus"],
            "multi_l": multi,
        }
    )
    return 0


def cmd_check_split_ready(revision_dir: Path) -> int:
    rev = Path(revision_dir).resolve()
    try:
        tree = load_dependency_tree(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(f"dependency tree not ready: {exc}")
    if tree.get("status") != "locked":
        return _emit_error("dependency tree status must be locked")
    try:
        pointer = load_discussion_pointer(rev)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _emit_error(f"discussion pointer not ready: {exc}")

    node_ids = [str(n["id"]) for n in tree["nodes"]]
    multi = len(node_ids) >= 2
    rulers_ok = False
    rulers_path = slice_rulers_path(rev)
    if multi:
        if not rulers_path.is_file():
            return _emit_error(
                "multi-L requires locked slice-rulers.json (run split-runner lock)"
            )
        try:
            rulers = load_slice_rulers(rev)
        except (ValueError, json.JSONDecodeError) as exc:
            return _emit_error(str(exc))
        if rulers.get("status") != "locked":
            return _emit_error("slice-rulers status must be locked")
        r_errors = validate_slice_rulers(rulers, required_node_ids=node_ids)
        if r_errors:
            return _emit_error("; ".join(r_errors))
        rulers_ok = True
    else:
        rulers_ok = True  # single-L exempt

    intake_complete = False
    if split_intake_path(rev).is_file():
        try:
            intake = load_split_intake(rev)
            intake_complete = intake.get("status") == "complete"
        except (ValueError, json.JSONDecodeError):
            intake_complete = False

    _emit(
        {
            "ok": True,
            "command": "check-split-ready",
            "tree_locked": True,
            "multi_l": multi,
            "rulers_ok": rulers_ok,
            "focus": pointer.get("focus"),
            "node_ids": node_ids,
            "intake_complete": intake_complete,
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

    p_wi = sub.add_parser("write-intake", help="Write split-intake.json (draft)")
    p_wi.add_argument("--intake-json", default=None)
    p_wi.add_argument("--intake-file", type=Path, default=None)

    p_ci = sub.add_parser("complete-intake", help="Mark intake complete")
    p_ci.add_argument("--confirm", action="store_true")

    p_lock = sub.add_parser(
        "lock-tree",
        help="Lock dependency tree + pointer + Lx/ (+ rulers when multi-L)",
    )
    p_lock.add_argument("--tree-json", default=None)
    p_lock.add_argument("--tree-file", type=Path, default=None)
    p_lock.add_argument("--rulers-json", default=None)
    p_lock.add_argument("--rulers-file", type=Path, default=None)
    p_lock.add_argument("--confirm", action="store_true")

    sub.add_parser(
        "check-split-ready",
        help="Assert locked tree (+ locked rulers when multi-L)",
    )

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
    if args.command == "write-intake":
        return cmd_write_intake(
            rev,
            intake_json=args.intake_json,
            intake_file=args.intake_file,
        )
    if args.command == "complete-intake":
        return cmd_complete_intake(rev, confirm=bool(args.confirm))
    if args.command == "lock-tree":
        return cmd_lock_tree(
            rev,
            tree_json=args.tree_json,
            tree_file=args.tree_file,
            rulers_json=args.rulers_json,
            rulers_file=args.rulers_file,
            confirm=bool(args.confirm),
        )
    if args.command == "check-split-ready":
        return cmd_check_split_ready(rev)
    if args.command == "assemble-index":
        return cmd_assemble_index(rev, confirm=bool(args.confirm))
    return _emit_error(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
