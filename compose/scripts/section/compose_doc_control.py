#!/usr/bin/env python3
"""Incremental compose document writer for initializing-runner.

Chapter grammar only (``append-chapter`` / ``init-doc``). Section-key write
subcommands retired in K3-d — see ``chapter_doc_schema.py``.

Subcommands:
    init-doc              Write document preamble (create or overwrite)
    append-chapter        Append one chapter fragment (fact-first display layer)

CLI details: ``python3 compose_doc_control.py --help``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402
from chapter_doc_schema import (  # noqa: E402
    chapter_anchor_present,
    format_chapter_anchor,
    has_any_chapter_anchor,
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


def compose_preamble(*, preamble: str) -> str:
    """Return normalized preamble markdown."""
    text = preamble
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def init_doc(path: Path, *, preamble: str) -> None:
    """Create or overwrite compose document with preamble only."""
    _atomic_write(path, compose_preamble(preamble=preamble))


def render_chapter_fragment(cid: str, display_title: str, body: str, *, is_first: bool) -> str:
    """Return markdown fragment for one chapter append (fact-first display layer).

    Chapter separation is call-order — the caller iterates framework ∩ placement
    chapter ids (``chapter_plan_control list-chapters``); this function only
    decides whether to prepend a visual ``---`` separator.
    """
    lines: list[str] = []
    if not is_first:
        lines.extend(["", "---", ""])
    lines.append(format_chapter_anchor(cid))
    title = display_title.strip() or "（待补）"
    lines.append(f"## {title}")
    lines.append("")
    stripped_body = body.strip()
    if stripped_body:
        lines.append(stripped_body)
    fragment = "\n".join(lines)
    if not fragment.endswith("\n"):
        fragment += "\n"
    return fragment


def append_chapter(
    path: Path,
    *,
    cid: str,
    display_title: str,
    body: str,
) -> None:
    """Append one chapter fragment to an existing compose document (Step 5)."""
    key = str(cid).strip()
    if not key:
        raise ValueError("cid must be a non-empty string")
    if not display_title.strip():
        raise ValueError("display_title must be a non-empty string")

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if chapter_anchor_present(existing, key):
        raise ValueError(f"chapter anchor already present: {key}")

    fragment = render_chapter_fragment(
        key,
        display_title,
        body,
        is_first=not has_any_chapter_anchor(existing),
    )
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _atomic_write(path, existing + fragment)


def _read_chapter_derive_display_title(revision_dir: Path, cid: str) -> str | None:
    key = str(cid).strip()
    path = chapter_derive_path(revision_dir, key)
    if not path.is_file():
        print(f"chapter derive artifact not found: {path}", file=sys.stderr)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid chapter derive JSON in {path.name}: {exc}", file=sys.stderr)
        return None
    title = str((data or {}).get("display_title", "")).strip()
    if not title:
        print(f"display_title missing in chapter derive for {key}", file=sys.stderr)
        return None
    return title


def _resolve_append_chapter_inputs(args: argparse.Namespace) -> tuple[str, str] | None:
    """Return (display_title, body) or None when argv combination is invalid."""
    has_revision = args.revision_dir is not None
    has_inline_title = args.display_title is not None
    has_inline_body = args.body is not None

    if has_revision and (has_inline_title or has_inline_body):
        print(
            "append-chapter: --revision-dir is mutually exclusive with "
            "--display-title and --body",
            file=sys.stderr,
        )
        return None

    if has_revision:
        revision_dir = args.revision_dir.resolve()
        cid = args.chapter_id.strip()
        body_file = chapter_body_path(revision_dir, cid)
        if not body_file.is_file():
            print(f"chapter body artifact not found: {body_file}", file=sys.stderr)
            return None
        body = body_file.read_text(encoding="utf-8")
        display_title = _read_chapter_derive_display_title(revision_dir, cid)
        if display_title is None:
            return None
        return display_title, body

    if args.display_title is None:
        print("append-chapter requires --display-title or --revision-dir", file=sys.stderr)
        return None
    display_title = args.display_title.strip()
    if not display_title:
        print("append-chapter: --display-title must be non-empty", file=sys.stderr)
        return None
    body = args.body if args.body is not None else ""
    return display_title, body


def cmd_append_chapter(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if not path.exists():
        print(f"compose document not found: {path}", file=sys.stderr)
        return 1

    resolved = _resolve_append_chapter_inputs(args)
    if resolved is None:
        return 1
    display_title, body = resolved

    try:
        append_chapter(path, cid=args.chapter_id, display_title=display_title, body=body)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{path.as_posix()}:{args.chapter_id.strip()}")
    return 0


def cmd_init_doc(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    preamble = _read_text_arg(inline=args.preamble, file_path=args.preamble_file)
    if not preamble.strip():
        print("init-doc requires --preamble or --preamble-file", file=sys.stderr)
        return 1
    init_doc(path, preamble=preamble)
    print(path.as_posix())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incremental compose document control")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-doc", help="Write preamble to compose document")
    init_parser.add_argument("--path", type=Path, required=True)
    init_parser.add_argument("--preamble", type=str, default=None)
    init_parser.add_argument("--preamble-file", type=Path, default=None)

    append_chapter_parser = sub.add_parser(
        "append-chapter",
        help="Append one chapter fragment (fact-first display layer)",
    )
    append_chapter_parser.add_argument("--path", type=Path, required=True)
    append_chapter_parser.add_argument("--chapter-id", type=str, required=True)
    append_chapter_parser.add_argument("--revision-dir", type=Path, default=None)
    append_chapter_parser.add_argument("--display-title", type=str, default=None)
    append_chapter_parser.add_argument("--body", type=str, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init-doc":
        return cmd_init_doc(args)
    if args.command == "append-chapter":
        return cmd_append_chapter(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
