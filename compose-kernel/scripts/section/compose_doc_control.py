#!/usr/bin/env python3
"""Incremental compose document writer for initializing-runner I2f.

Subcommands:
    init-doc        Write document preamble (create or overwrite)
    append-intent   Append one outline intent block (H2/H3/body/---);
                    requires --display-title or --display-title-file, and body via
                    --body or --body-file

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


def _resolve_display_title(*, inline: str | None, file_path: Path | None) -> str:
    """Return display title from inline string or first line of title file."""
    if file_path is not None:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return lines[0].strip() if lines else ""
    if inline is not None:
        return inline.strip()
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


def compose_preamble(*, preamble: str, preamble_addon: str = "") -> str:
    """Return normalized preamble markdown."""
    text = preamble
    if preamble_addon:
        if text and not text.endswith("\n"):
            text += "\n"
        text += preamble_addon
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def init_doc(path: Path, *, preamble: str, preamble_addon: str = "") -> None:
    """Create or overwrite compose document with preamble only."""
    _atomic_write(path, compose_preamble(preamble=preamble, preamble_addon=preamble_addon))


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


def cmd_init_doc(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    preamble = _read_text_arg(inline=args.preamble, file_path=args.preamble_file)
    addon = _read_text_arg(inline=args.preamble_addon, file_path=args.preamble_addon_file)
    if not preamble.strip() and not addon.strip():
        print("init-doc requires --preamble or --preamble-file", file=sys.stderr)
        return 1
    init_doc(path, preamble=preamble, preamble_addon=addon)
    print(path.as_posix())
    return 0


def cmd_append_intent(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if not path.exists():
        print(f"compose document not found: {path}", file=sys.stderr)
        return 1
    if args.display_title is None and args.display_title_file is None:
        print(
            "append-intent requires --display-title or --display-title-file",
            file=sys.stderr,
        )
        return 1
    body = _read_text_arg(inline=args.body, file_path=args.body_file)
    display_title = _resolve_display_title(
        inline=args.display_title,
        file_path=args.display_title_file.resolve() if args.display_title_file else None,
    )
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incremental compose document control")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-doc", help="Write preamble to compose document")
    init_parser.add_argument("--path", type=Path, required=True)
    init_parser.add_argument("--preamble", type=str, default=None)
    init_parser.add_argument("--preamble-file", type=Path, default=None)
    init_parser.add_argument("--preamble-addon", type=str, default=None)
    init_parser.add_argument("--preamble-addon-file", type=Path, default=None)

    append_parser = sub.add_parser("append-intent", help="Append one intent block")
    append_parser.add_argument("--path", type=Path, required=True)
    append_parser.add_argument("--section", type=str, required=True)
    append_parser.add_argument("--display-title", type=str, default=None)
    append_parser.add_argument("--display-title-file", type=Path, default=None)
    append_parser.add_argument("--body", type=str, default=None)
    append_parser.add_argument("--body-file", type=Path, default=None)
    append_parser.add_argument("--outline-path", type=Path, default=None)
    append_parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    append_parser.add_argument("--project-root", type=Path, default=Path("."))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init-doc":
        return cmd_init_doc(args)
    if args.command == "append-intent":
        return cmd_append_intent(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
