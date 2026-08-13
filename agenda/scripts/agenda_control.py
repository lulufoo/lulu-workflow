#!/usr/bin/env python3
"""CLI control for stage agenda (agenda.json).

Subcommands:
    add     Add blocker|note (session-resolved revision, or --revision-dir)
    update  Change status / async / text / reason
    list    List items (optional --blocking-only)
    menu    Print available commands / L1 option keys (JSON)

Default location: cycle cache ``session-state.md`` ``active_doc`` → ``revision{N}/``.
Pass ``--project-root`` ``--cycle-id`` (same identity as compose session
controls; ``profile_id`` comes from compose start context). ``--revision-dir``
is an optional override (tests / escape hatch).

Design rationale (source repo, why-only):
docs/domain/archive/workflow/stage-agenda-design.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agenda_schema import (  # noqa: E402
    AGENDA_CLASSES,
    AGENDA_STATUSES,
    agenda_path,
    blocking_items,
    find_item,
    load_agenda,
    mint_item_id,
    next_item_seq,
    normalize_item,
    save_agenda,
)
from agenda_session import (  # noqa: E402
    resolve_revision_dir,
)

_SESSION_FLAGS = (
    "--project-root $(pwd) --cycle-id $CYCLE_ID"
)

_MENU = {
    "commands": [
        {
            "key": "add",
            "cli": (
                f"add {_SESSION_FLAGS} --class blocker|note --text <text> [--async]"
            ),
            "l1": "agenda 新增 blocker / agenda 新增 note",
        },
        {
            "key": "update",
            "cli": (
                f"update {_SESSION_FLAGS} --id A-n "
                "[--status open|released|waived] [--async|--no-async] "
                "[--text <text>] [--reason <reason>]"
            ),
            "l1": "agenda 更新项",
        },
        {
            "key": "list",
            "cli": f"list {_SESSION_FLAGS} [--blocking-only]",
            "l1": "agenda 查看 blocker list / agenda 查看全部",
        },
        {
            "key": "menu",
            "cli": "menu",
            "l1": "agenda 查看命令",
        },
    ],
    "l1_options": [
        {"key": "menu", "label": "agenda 查看命令"},
        {"key": "add_blocker", "label": "agenda 新增 blocker"},
        {"key": "add_note", "label": "agenda 新增 note"},
        {"key": "set_async", "label": "agenda 标为异步"},
        {"key": "clear_async", "label": "agenda 取消异步"},
        {"key": "release", "label": "agenda 已做完"},
        {"key": "waive", "label": "agenda 放弃"},
        {"key": "list_blocking", "label": "agenda 查看 blocker list"},
        {"key": "list_all", "label": "agenda 查看全部"},
        {"key": "update", "label": "agenda 更新项"},
    ],
}


def _emit(payload: dict[str, Any], *, ok: bool = True) -> int:
    payload = {"ok": ok, **payload}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def _fail(message: str) -> int:
    return _emit({"error": message}, ok=False)


def _revision_dir_from_args(args: argparse.Namespace) -> Path:
    override = getattr(args, "revision_dir", None)
    if override:
        return Path(override)
    root = Path(args.project_root).resolve()
    return resolve_revision_dir(
        root,
        cycle_id=args.cycle_id,
        profile_id="",
    )


def cmd_add(args: argparse.Namespace) -> int:
    klass = str(args.item_class).strip().lower()
    if klass not in AGENDA_CLASSES:
        return _fail(f"class must be one of {sorted(AGENDA_CLASSES)}")
    text = (args.text or "").strip()
    if not text:
        return _fail("text is required")
    is_async = bool(args.is_async)
    if klass == "note" and is_async:
        return _fail("note must not set --async")

    try:
        rev = _revision_dir_from_args(args)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))

    path = agenda_path(rev)
    data = load_agenda(path)
    items = list(data.get("items") or [])
    item_id = mint_item_id(next_item_seq(items))
    raw: dict[str, Any] = {
        "id": item_id,
        "class": klass,
        "status": "open",
        "text": text,
    }
    if klass == "blocker":
        raw["async"] = is_async
    item = normalize_item(raw)
    items.append(item)
    data = {"version": int(data.get("version") or 1), "items": items}
    try:
        save_agenda(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _emit(
        {
            "command": "add",
            "item": item,
            "path": str(path),
            "revision_dir": str(rev),
        }
    )


def cmd_update(args: argparse.Namespace) -> int:
    item_id = (args.id or "").strip()
    if not item_id:
        return _fail("--id is required")

    try:
        rev = _revision_dir_from_args(args)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))

    path = agenda_path(rev)
    data = load_agenda(path)
    existing = find_item(data, item_id)
    if existing is None:
        return _fail(f"agenda item not found: {item_id}")

    merged = dict(existing)
    if args.status is not None:
        status = str(args.status).strip().lower()
        if status not in AGENDA_STATUSES:
            return _fail(f"status must be one of {sorted(AGENDA_STATUSES)}")
        merged["status"] = status
    if args.text is not None:
        text = args.text.strip()
        if not text:
            return _fail("text must be non-empty when provided")
        merged["text"] = text
    if args.async_set is not None:
        if str(merged.get("class", "")).lower() != "blocker":
            return _fail("async only applies to blocker")
        merged["async"] = bool(args.async_set)
    if args.reason is not None:
        merged["reason"] = args.reason.strip()

    if str(merged.get("status", "")).lower() == "waived":
        if not str(merged.get("reason", "")).strip():
            return _fail("reason is required when status=waived")

    item = normalize_item(merged)
    new_items: list[dict[str, Any]] = []
    for it in data.get("items") or []:
        if isinstance(it, dict) and str(it.get("id", "")).strip() == item_id:
            new_items.append(item)
        elif isinstance(it, dict):
            new_items.append(it)
    data = {"version": int(data.get("version") or 1), "items": new_items}
    try:
        save_agenda(path, data)
    except ValueError as exc:
        return _fail(str(exc))
    return _emit(
        {
            "command": "update",
            "item": item,
            "path": str(path),
            "revision_dir": str(rev),
        }
    )


def cmd_list(args: argparse.Namespace) -> int:
    try:
        rev = _revision_dir_from_args(args)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _fail(str(exc))

    path = agenda_path(rev)
    data = load_agenda(path)
    items = list(data.get("items") or [])
    if args.blocking_only:
        items = blocking_items(data)
    return _emit(
        {
            "command": "list",
            "blocking_only": bool(args.blocking_only),
            "items": items,
            "path": str(path),
            "revision_dir": str(rev),
            "exists": path.is_file(),
        }
    )


def cmd_menu(_: argparse.Namespace) -> int:
    return _emit({"command": "menu", **_MENU})


def _add_session_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--project-root",
        default=".",
        help="project root (default: cwd)",
    )
    p.add_argument(
        "--cycle-id",
        default=None,
        help="cycle id (default: $LULU_CYCLE_ID)",
    )
    p.add_argument(
        "--revision-dir",
        default=None,
        help="optional override; otherwise resolved from session-state active_doc",
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agenda_control.py",
        description=(
            "Stage agenda control. Prefer --cycle-id to resolve "
            "revision{N} from session-state; --revision-dir overrides."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add agenda item")
    _add_session_args(p_add)
    p_add.add_argument(
        "--class",
        dest="item_class",
        required=True,
        choices=sorted(AGENDA_CLASSES),
    )
    p_add.add_argument("--text", required=True)
    p_add.add_argument(
        "--async",
        dest="is_async",
        action="store_true",
        default=False,
        help="blocker only: track without blocking deliver",
    )
    p_add.set_defaults(func=cmd_add)

    p_up = sub.add_parser("update", help="Update agenda item")
    _add_session_args(p_up)
    p_up.add_argument("--id", required=True)
    p_up.add_argument("--status", choices=sorted(AGENDA_STATUSES))
    p_up.add_argument("--text")
    p_up.add_argument("--reason")
    async_g = p_up.add_mutually_exclusive_group()
    async_g.add_argument(
        "--async",
        dest="async_set",
        action="store_true",
        default=None,
        help="set blocker async=true",
    )
    async_g.add_argument(
        "--no-async",
        dest="async_set",
        action="store_false",
        help="set blocker async=false",
    )
    p_up.set_defaults(func=cmd_update)

    p_list = sub.add_parser("list", help="List agenda items")
    _add_session_args(p_list)
    p_list.add_argument(
        "--blocking-only",
        action="store_true",
        help="only blocker ∧ open ∧ ¬async",
    )
    p_list.set_defaults(func=cmd_list)

    p_menu = sub.add_parser("menu", help="List available commands / L1 options")
    p_menu.set_defaults(func=cmd_menu)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
