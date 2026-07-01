#!/usr/bin/env python3
"""Incremental compose document writer for initializing-runner I2e–I2g.

Subcommands:
    init-doc              Write document preamble (create or overwrite)
    set-display-title     Persist one section display title in _title-display.json
    set-block-title       Persist one block reader title in _title-block.json
    append-intent         Append one outline intent block (H2/H3/body/---)
    patch-block-heading   Replace outline H2 placeholder with reader block title

CLI details: ``python3 compose_doc_control.py --help``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_doc_schema import format_section_intent_heading  # noqa: E402
from init_artifact_paths import block_titles_path, body_path, display_titles_path  # noqa: E402
from init_block_titles_schema import (  # noqa: E402
    get_block_title,
    load_block_titles,
    set_block_title,
)
from init_display_titles_schema import (  # noqa: E402
    get_display_title,
    load_display_titles,
    set_display_title,
)
from outline_registry_schema import load_outline_registry, normalize_outline_registry  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402

_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _read_text_arg(*, inline: str | None, file_path: Path | None) -> str:
    if file_path is not None:
        return file_path.read_text(encoding="utf-8")
    if inline is not None:
        return inline
    return ""


def _load_outline(*, outline_path: Path | None, project_root: Path, profile_id: str) -> dict[str, Any]:
    if outline_path is not None:
        data = json.loads(outline_path.read_text(encoding="utf-8"))
        return normalize_outline_registry(data)
    return load_outline_registry(project_root, profile_id=profile_id)


def build_outline_intent_layout(outline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return intent_key → layout metadata for append-intent."""
    blocks = outline.get("blocks") or {}
    block_order = [str(key).upper() for key in outline.get("outline_order") or []]
    layout: dict[str, dict[str, Any]] = {}
    for block_index, block_key in enumerate(block_order):
        block = blocks.get(block_key) or {}
        heading = str(block.get("heading", "")).strip()
        intents = [str(item).upper() for item in block.get("intents") or []]
        last_block = block_index == len(block_order) - 1
        for intent_index, intent_key in enumerate(intents):
            layout[intent_key] = {
                "block_key": block_key,
                "block_heading": heading,
                "block_index": block_index,
                "first_in_block": intent_index == 0,
                "last_in_block": intent_index == len(intents) - 1,
                "last_block": last_block,
            }
    return layout


def compose_preamble(*, preamble: str) -> str:
    """Return normalized preamble markdown."""
    text = preamble
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def init_doc(path: Path, *, preamble: str) -> None:
    """Create or overwrite compose document with preamble only."""
    _atomic_write(path, compose_preamble(preamble=preamble))


def _section_anchor_present(text: str, section_key: str) -> bool:
    key = section_key.strip().upper()
    for match in _SECTION_KEY_ANCHOR_RE.finditer(text):
        if match.group(1).upper() == key:
            return True
    return False


def render_intent_fragment(
    section_key: str,
    display_title: str,
    body: str,
    *,
    layout: dict[str, Any],
) -> str:
    """Return markdown fragment for one intent append."""
    lines: list[str] = []
    if layout["first_in_block"]:
        if layout["block_index"] > 0:
            lines.extend(["", "---", ""])
        lines.extend([f"## {layout['block_heading']}", ""])
    lines.append(format_section_intent_heading(section_key, display_title))
    lines.append("")
    stripped_body = body.strip()
    if stripped_body:
        lines.append(stripped_body)
    fragment = "\n".join(lines)
    if not fragment.endswith("\n"):
        fragment += "\n"
    return fragment


def append_intent(
    path: Path,
    *,
    section_key: str,
    display_title: str,
    body: str,
    outline: dict[str, Any],
) -> None:
    """Append one intent section to an existing compose document."""
    key = section_key.strip().upper()
    layout_map = build_outline_intent_layout(outline)
    if key not in layout_map:
        raise ValueError(f"section {key!r} not found in outline-registry intents")

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if _section_anchor_present(existing, key):
        raise ValueError(f"section-key anchor already present: {key}")

    layout = layout_map[key]
    fragment = render_intent_fragment(key, display_title, body, layout=layout)
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _atomic_write(path, existing + fragment)


def patch_block_heading(
    path: Path,
    *,
    block_key: str,
    title: str,
    outline: dict[str, Any],
) -> None:
    """Replace the unique ``## {blocks.{key}.heading}`` placeholder with reader title."""
    bk = block_key.strip().upper()
    blocks = outline.get("blocks") or {}
    block = blocks.get(bk)
    if not isinstance(block, dict):
        raise ValueError(f"block {bk!r} not found in outline-registry")

    placeholder = str(block.get("heading", "")).strip()
    if not placeholder:
        raise ValueError(f"blocks.{bk}.heading is empty")

    new_title = title.strip()
    if not new_title:
        raise ValueError("block display title is empty")

    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^##\s+{re.escape(placeholder)}\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError(
            f"placeholder heading not found for block {bk}: ## {placeholder}",
        )
    if len(matches) > 1:
        raise ValueError(
            f"ambiguous placeholder heading for block {bk}: {len(matches)} matches",
        )

    start, end = matches[0].span()
    replacement = f"## {new_title}"
    _atomic_write(path, text[:start] + replacement + text[end:])


def _resolve_append_inputs(args: argparse.Namespace) -> tuple[str, str] | None:
    """Return (display_title, body) or None when argv combination is invalid."""
    has_revision = args.revision_dir is not None
    has_inline_title = args.display_title is not None
    has_inline_body = args.body is not None

    if has_revision and (has_inline_title or has_inline_body):
        print(
            "append-intent: --revision-dir is mutually exclusive with "
            "--display-title and --body",
            file=sys.stderr,
        )
        return None

    if has_revision:
        revision_dir = args.revision_dir.resolve()
        section = args.section.strip().upper()
        body_file = body_path(revision_dir, section)
        if not body_file.is_file():
            print(f"body artifact not found: {body_file}", file=sys.stderr)
            return None
        body = body_file.read_text(encoding="utf-8")
        try:
            titles = load_display_titles(display_titles_path(revision_dir))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return None
        display_title = get_display_title(titles, section)
        if not display_title:
            print(
                f"display title missing in _title-display.json for section {section}",
                file=sys.stderr,
            )
            return None
        return display_title, body

    if args.display_title is None:
        print("append-intent requires --display-title or --revision-dir", file=sys.stderr)
        return None
    display_title = args.display_title.strip()
    body = args.body if args.body is not None else ""
    return display_title, body


def cmd_init_doc(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    preamble = _read_text_arg(inline=args.preamble, file_path=args.preamble_file)
    if not preamble.strip():
        print("init-doc requires --preamble or --preamble-file", file=sys.stderr)
        return 1
    init_doc(path, preamble=preamble)
    print(path.as_posix())
    return 0


def cmd_set_display_title(args: argparse.Namespace) -> int:
    try:
        out_path = set_display_title(
            args.revision_dir.resolve(),
            args.section,
            args.title,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    key = args.section.strip().upper()
    print(f"{out_path.as_posix()}:{key}")
    return 0


def cmd_set_block_title(args: argparse.Namespace) -> int:
    try:
        out_path = set_block_title(
            args.revision_dir.resolve(),
            args.block_key,
            args.title,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    key = args.block_key.strip().upper()
    print(f"{out_path.as_posix()}:{key}")
    return 0


def cmd_append_intent(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if not path.exists():
        print(f"compose document not found: {path}", file=sys.stderr)
        return 1

    resolved = _resolve_append_inputs(args)
    if resolved is None:
        return 1
    display_title, body = resolved

    profile_id = (args.profile or DEFAULT_COMPOSE_PROFILE_ID).strip() or DEFAULT_COMPOSE_PROFILE_ID
    project_root = args.project_root.resolve()
    try:
        outline = _load_outline(
            outline_path=args.outline_path.resolve() if args.outline_path else None,
            project_root=project_root,
            profile_id=profile_id,
        )
        append_intent(
            path,
            section_key=args.section,
            display_title=display_title,
            body=body,
            outline=outline,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{path.as_posix()}:{args.section.strip().upper()}")
    return 0


def _resolve_patch_title(args: argparse.Namespace) -> str | None:
    has_revision = args.revision_dir is not None
    has_inline = args.title is not None
    if has_revision and has_inline:
        print(
            "patch-block-heading: --revision-dir is mutually exclusive with --title",
            file=sys.stderr,
        )
        return None
    if has_revision:
        revision_dir = args.revision_dir.resolve()
        block_key = args.block_key.strip().upper()
        try:
            titles = load_block_titles(block_titles_path(revision_dir))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return None
        title = get_block_title(titles, block_key)
        if not title:
            print(
                f"block title missing in _title-block.json for block {block_key}",
                file=sys.stderr,
            )
            return None
        return title
    if args.title is None:
        print(
            "patch-block-heading requires --title or --revision-dir",
            file=sys.stderr,
        )
        return None
    return args.title.strip()


def cmd_patch_block_heading(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if not path.exists():
        print(f"compose document not found: {path}", file=sys.stderr)
        return 1

    title = _resolve_patch_title(args)
    if title is None:
        return 1

    profile_id = (args.profile or DEFAULT_COMPOSE_PROFILE_ID).strip() or DEFAULT_COMPOSE_PROFILE_ID
    project_root = args.project_root.resolve()
    try:
        outline = _load_outline(
            outline_path=args.outline_path.resolve() if args.outline_path else None,
            project_root=project_root,
            profile_id=profile_id,
        )
        patch_block_heading(
            path,
            block_key=args.block_key,
            title=title,
            outline=outline,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    block_key = args.block_key.strip().upper()
    print(f"{path.as_posix()}:{block_key}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incremental compose document control")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-doc", help="Write preamble to compose document")
    init_parser.add_argument("--path", type=Path, required=True)
    init_parser.add_argument("--preamble", type=str, default=None)
    init_parser.add_argument("--preamble-file", type=Path, default=None)

    display_parser = sub.add_parser(
        "set-display-title",
        help="Set one section display title in _title-display.json",
    )
    display_parser.add_argument("--revision-dir", type=Path, required=True)
    display_parser.add_argument("--section", type=str, required=True)
    display_parser.add_argument("--title", type=str, required=True)

    block_title_parser = sub.add_parser(
        "set-block-title",
        help="Set one block reader title in _title-block.json",
    )
    block_title_parser.add_argument("--revision-dir", type=Path, required=True)
    block_title_parser.add_argument("--block-key", type=str, required=True)
    block_title_parser.add_argument("--title", type=str, required=True)

    append_parser = sub.add_parser("append-intent", help="Append one intent block")
    append_parser.add_argument("--path", type=Path, required=True)
    append_parser.add_argument("--section", type=str, required=True)
    append_parser.add_argument("--revision-dir", type=Path, default=None)
    append_parser.add_argument("--display-title", type=str, default=None)
    append_parser.add_argument("--body", type=str, default=None)
    append_parser.add_argument("--outline-path", type=Path, default=None)
    append_parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    append_parser.add_argument("--project-root", type=Path, default=Path("."))

    patch_parser = sub.add_parser(
        "patch-block-heading",
        help="Replace outline H2 placeholder with reader block title",
    )
    patch_parser.add_argument("--path", type=Path, required=True)
    patch_parser.add_argument("--block-key", type=str, required=True)
    patch_parser.add_argument("--revision-dir", type=Path, default=None)
    patch_parser.add_argument("--title", type=str, default=None)
    patch_parser.add_argument("--outline-path", type=Path, default=None)
    patch_parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    patch_parser.add_argument("--project-root", type=Path, default=Path("."))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init-doc":
        return cmd_init_doc(args)
    if args.command == "set-display-title":
        return cmd_set_display_title(args)
    if args.command == "set-block-title":
        return cmd_set_block_title(args)
    if args.command == "append-intent":
        return cmd_append_intent(args)
    if args.command == "patch-block-heading":
        return cmd_patch_block_heading(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
