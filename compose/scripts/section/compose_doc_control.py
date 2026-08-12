#!/usr/bin/env python3
"""Incremental compose document writer for writing-runner.

Chapter grammar (``init-doc`` / ``append-chapter`` / ``assemble-arc``).
Archive-5.0 assemble presentation: tree group/leaf headings + lens chapters
as anchors (default omit lens heading).

Subcommands:
    init-doc              Write document preamble (create or overwrite)
    append-chapter        Append one chapter fragment
    assemble-arc          Assemble full doc from ``_narrative-arc.json`` + bodies

CLI details: ``python3 compose_doc_control.py --help``

Process how:
docs/domain/archive/compose/archive-5.0/compose-narrative-arc-assemble-presentation-design.md
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

from logs.workflow_log import emit_biz  # noqa: E402
from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402
from chapter_doc_schema import (  # noqa: E402
    chapter_anchor_present,
    format_chapter_anchor,
    has_any_chapter_anchor,
)
from discussion_pointer_schema import active_slice_dir  # noqa: E402
from narrative_arc_schema import (  # noqa: E402
    is_write_ready,
    load_narrative_arc,
    narrative_arc_path,
)

_LENS_HEADING_VALUES = frozenset({"omit", "show"})
_TREE_MODE_VALUES = frozenset({"auto", "require", "ignore"})
_MAX_HEADING_LEVEL = 6


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


def _normalize_lens_heading(value: str | None) -> str:
    mode = str(value or "omit").strip().lower()
    if mode not in _LENS_HEADING_VALUES:
        raise ValueError(
            f"lens_heading must be one of {sorted(_LENS_HEADING_VALUES)} "
            f"(got {value!r})"
        )
    return mode


def render_heading(level: int, title: str) -> str:
    """Return an ATX heading line for ``title`` at ``level`` (2..6)."""
    depth = max(2, min(int(level), _MAX_HEADING_LEVEL))
    text = title.strip() or "（待补）"
    return f"{'#' * depth} {text}"


def render_chapter_fragment(
    cid: str,
    body: str,
    *,
    lens_heading: str = "omit",
    display_title: str = "",
    is_first: bool = True,
    use_separator: bool = True,
) -> str:
    """Return markdown fragment for one lens chapter.

    ``lens_heading=omit`` (default): anchor + body only.
    ``lens_heading=show``: anchor + ``#### {display_title|（待补）}`` + body.
    """
    mode = _normalize_lens_heading(lens_heading)
    lines: list[str] = []
    if use_separator and not is_first:
        lines.extend(["", "---", ""])
    elif not is_first:
        lines.append("")
    lines.append(format_chapter_anchor(cid))
    if mode == "show":
        label = display_title.strip() or "（待补）"
        lines.append(f"#### {label}")
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
    body: str,
    lens_heading: str = "omit",
    display_title: str = "",
) -> None:
    """Append one chapter fragment to an existing compose document."""
    key = str(cid).strip()
    if not key:
        raise ValueError("cid must be a non-empty string")
    mode = _normalize_lens_heading(lens_heading)
    if mode == "show" and not str(display_title).strip():
        raise ValueError("display_title must be a non-empty string when lens_heading=show")

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if chapter_anchor_present(existing, key):
        raise ValueError(f"chapter anchor already present: {key}")

    fragment = render_chapter_fragment(
        key,
        body,
        lens_heading=mode,
        display_title=display_title,
        is_first=not has_any_chapter_anchor(existing),
        use_separator=True,
    )
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _atomic_write(path, existing + fragment)


def _read_chapter_derive(revision_dir: Path, cid: str) -> dict[str, Any] | None:
    key = str(cid).strip()
    path = chapter_derive_path(revision_dir, key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid chapter derive JSON in {path.name}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"chapter derive must be an object: {path.name}", file=sys.stderr)
        return None
    return data


def _read_chapter_derive_display_title(revision_dir: Path, cid: str) -> str | None:
    data = _read_chapter_derive(revision_dir, cid)
    if data is None:
        path = chapter_derive_path(revision_dir, cid)
        if not path.is_file():
            print(f"chapter derive artifact not found: {path}", file=sys.stderr)
        return None
    title = str(data.get("display_title", "")).strip()
    if not title:
        print(f"display_title missing in chapter derive for {cid}", file=sys.stderr)
        return None
    return title


def _resolve_append_chapter_inputs(
    args: argparse.Namespace,
) -> tuple[str, str, str] | None:
    """Return (display_title, body, lens_heading) or None when invalid."""
    try:
        mode = _normalize_lens_heading(getattr(args, "lens_heading", "omit"))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return None

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
        display_title = ""
        if mode == "show":
            title = _read_chapter_derive_display_title(revision_dir, cid)
            if title is None:
                return None
            display_title = title
        return display_title, body, mode

    body = args.body if args.body is not None else ""
    display_title = (args.display_title or "").strip()
    if mode == "show":
        if args.display_title is None:
            print(
                "append-chapter with lens_heading=show requires "
                "--display-title or --revision-dir",
                file=sys.stderr,
            )
            return None
        if not display_title:
            print("append-chapter: --display-title must be non-empty", file=sys.stderr)
            return None
    elif args.display_title is None and args.body is None:
        print(
            "append-chapter requires --body (and optionally --display-title) "
            "or --revision-dir",
            file=sys.stderr,
        )
        return None
    return display_title, body, mode


def cmd_append_chapter(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if not path.exists():
        print(f"compose document not found: {path}", file=sys.stderr)
        return 1

    resolved = _resolve_append_chapter_inputs(args)
    if resolved is None:
        return 1
    display_title, body, mode = resolved

    try:
        append_chapter(
            path,
            cid=args.chapter_id,
            body=body,
            lens_heading=mode,
            display_title=display_title,
        )
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


def _leaf_index(arc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for leaf in arc.get("leaves") or []:
        if not isinstance(leaf, dict):
            continue
        lid = str(leaf.get("id", "")).strip()
        if lid:
            out[lid] = leaf
    return out


def _chapter_units_for_leaf(leaf: dict[str, Any]) -> list[dict[str, str]]:
    leaf_id = str(leaf.get("id", "")).strip()
    units: list[dict[str, str]] = []
    for index, chapter in enumerate(leaf.get("chapters") or []):
        if not isinstance(chapter, dict):
            continue
        lens = str(chapter.get("lens", "")).strip().upper()
        cid = f"{leaf_id}-{lens}" if leaf_id and lens else f"{leaf_id}-C{index}"
        units.append({"chapter_id": cid, "lens": lens})
    return units


def _emit_leaf_chapters(
    parts: list[str],
    *,
    leaf: dict[str, Any],
    revision_dir: Path,
    lens_heading: str,
    emitted_cids: set[str],
) -> None:
    mode = _normalize_lens_heading(lens_heading)
    for unit in _chapter_units_for_leaf(leaf):
        cid = unit["chapter_id"]
        if cid in emitted_cids:
            raise ValueError(f"duplicate chapter id during assemble: {cid}")
        body_path = chapter_body_path(revision_dir, cid)
        if not body_path.is_file():
            raise ValueError(f"chapter body artifact not found: {body_path}")
        body = body_path.read_text(encoding="utf-8")
        display_title = unit["lens"]
        if mode == "show":
            derive = _read_chapter_derive(revision_dir, cid)
            if derive and str(derive.get("display_title", "")).strip():
                display_title = str(derive.get("display_title", "")).strip()
            elif not display_title:
                display_title = "（待补）"
        parts.append(
            render_chapter_fragment(
                cid,
                body,
                lens_heading=mode,
                display_title=display_title,
                is_first=True,
                use_separator=False,
            ).rstrip("\n")
        )
        parts.append("")
        emitted_cids.add(cid)


def _walk_tree_node(
    node: Any,
    *,
    level: int | None,
    leaf_map: dict[str, dict[str, Any]],
    parts: list[str],
    revision_dir: Path,
    lens_heading: str,
    emitted_cids: set[str],
    seen_leaves: set[str],
) -> None:
    if not isinstance(node, dict):
        raise ValueError("narrative_arc.tree nodes must be objects")
    nid = str(node.get("id", "")).strip()
    title = str(node.get("title", "")).strip()
    children = node.get("children") or []
    if children and not isinstance(children, list):
        raise ValueError(f"tree node {nid!r} children must be an array")

    if children:
        if level is not None:
            parts.append(render_heading(level, title or nid or "（待补）"))
            parts.append("")
        child_level = 2 if level is None else min(level + 1, _MAX_HEADING_LEVEL)
        for child in children:
            _walk_tree_node(
                child,
                level=child_level,
                leaf_map=leaf_map,
                parts=parts,
                revision_dir=revision_dir,
                lens_heading=lens_heading,
                emitted_cids=emitted_cids,
                seen_leaves=seen_leaves,
            )
        return

    if not nid:
        raise ValueError("tree leaf node requires non-empty id")
    if nid not in leaf_map:
        raise ValueError(f"tree node id not found in leaves: {nid!r}")
    if nid in seen_leaves:
        raise ValueError(f"tree references leaf more than once: {nid!r}")
    leaf = leaf_map[nid]
    leaf_title = title or str(leaf.get("title", "")).strip() or nid
    emit_level = 2 if level is None else level
    parts.append(render_heading(emit_level, leaf_title))
    parts.append("")
    _emit_leaf_chapters(
        parts,
        leaf=leaf,
        revision_dir=revision_dir,
        lens_heading=lens_heading,
        emitted_cids=emitted_cids,
    )
    seen_leaves.add(nid)


def assemble_arc_markdown(
    arc: dict[str, Any],
    *,
    revision_dir: Path,
    preamble: str,
    lens_heading: str = "omit",
    tree_mode: str = "auto",
) -> str:
    """Return full assembled markdown for a write_ready narrative arc."""
    mode = _normalize_lens_heading(lens_heading)
    tmode = str(tree_mode or "auto").strip().lower()
    if tmode not in _TREE_MODE_VALUES:
        raise ValueError(
            f"tree mode must be one of {sorted(_TREE_MODE_VALUES)} (got {tree_mode!r})"
        )
    if not is_write_ready(arc):
        raise ValueError("assemble-arc requires status=write_ready")

    leaf_map = _leaf_index(arc)
    if not leaf_map:
        raise ValueError("narrative_arc.leaves is empty")

    parts: list[str] = [compose_preamble(preamble=preamble).rstrip("\n"), ""]
    emitted_cids: set[str] = set()
    seen_leaves: set[str] = set()

    tree = arc.get("tree")
    use_tree = False
    if tmode == "require":
        if tree is None:
            raise ValueError("assemble-arc --tree require but narrative_arc.tree is missing")
        use_tree = True
    elif tmode == "auto":
        use_tree = tree is not None
    # ignore → use_tree False

    if use_tree:
        if isinstance(tree, list):
            for node in tree:
                _walk_tree_node(
                    node,
                    level=2,
                    leaf_map=leaf_map,
                    parts=parts,
                    revision_dir=revision_dir,
                    lens_heading=mode,
                    emitted_cids=emitted_cids,
                    seen_leaves=seen_leaves,
                )
        elif isinstance(tree, dict):
            _walk_tree_node(
                tree,
                level=None,
                leaf_map=leaf_map,
                parts=parts,
                revision_dir=revision_dir,
                lens_heading=mode,
                emitted_cids=emitted_cids,
                seen_leaves=seen_leaves,
            )
        else:
            raise ValueError("narrative_arc.tree must be an object or array")
        missing = [lid for lid in leaf_map if lid not in seen_leaves]
        if missing:
            raise ValueError(
                "tree does not cover all leaves: " + ", ".join(sorted(missing))
            )
    else:
        for leaf in arc.get("leaves") or []:
            if not isinstance(leaf, dict):
                continue
            lid = str(leaf.get("id", "")).strip()
            if not lid:
                continue
            title = str(leaf.get("title", "")).strip() or lid
            parts.append(render_heading(2, title))
            parts.append("")
            _emit_leaf_chapters(
                parts,
                leaf=leaf,
                revision_dir=revision_dir,
                lens_heading=mode,
                emitted_cids=emitted_cids,
            )
            seen_leaves.add(lid)

    text = "\n".join(parts).rstrip() + "\n"
    return text


def assemble_arc_to_path(
    path: Path,
    *,
    revision_dir: Path,
    preamble: str,
    lens_heading: str = "omit",
    tree_mode: str = "auto",
    skip_write_state: bool = False,
) -> dict[str, Any]:
    """Load arc from revision slice, assemble, and write ``path``."""
    slice_dir = active_slice_dir(revision_dir.resolve())
    if not skip_write_state:
        from chapter_write_state_schema import require_complete  # local: avoid cycle

        ws_err = require_complete(slice_dir)
        if ws_err:
            raise ValueError(ws_err)
    arc_path = narrative_arc_path(slice_dir)
    arc = load_narrative_arc(arc_path)
    text = assemble_arc_markdown(
        arc,
        revision_dir=slice_dir,
        preamble=preamble,
        lens_heading=lens_heading,
        tree_mode=tree_mode,
    )
    _atomic_write(path, text)
    leaf_count = len(_leaf_index(arc))
    return {
        "ok": True,
        "path": path.as_posix(),
        "arc_path": str(arc_path),
        "leaves": leaf_count,
        "lens_heading": _normalize_lens_heading(lens_heading),
        "tree_mode": str(tree_mode or "auto").strip().lower(),
    }


def cmd_assemble_arc(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    revision_dir = args.revision_dir.resolve()
    root = Path.cwd().resolve()
    conv_id = str(getattr(args, "conversation_id", "") or "").strip() or None
    preamble = _read_text_arg(inline=args.preamble, file_path=args.preamble_file)
    if not preamble.strip():
        print("assemble-arc requires --preamble or --preamble-file", file=sys.stderr)
        return 1
    emit_biz(
        component="compose-doc",
        event="assemble.start",
        conversation_id=conv_id,
        project_root=root,
        detail={"path": str(path), "revision_dir": str(revision_dir)},
    )
    try:
        result = assemble_arc_to_path(
            path,
            revision_dir=revision_dir,
            preamble=preamble,
            lens_heading=args.lens_heading,
            tree_mode=args.tree,
            skip_write_state=bool(args.skip_write_state),
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        emit_biz(
            component="compose-doc",
            event="assemble.error",
            conversation_id=conv_id,
            project_root=root,
            detail={"error": str(exc)},
        )
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    emit_biz(
        component="compose-doc",
        event="assemble.end",
        conversation_id=conv_id,
        project_root=root,
        detail={"path": str(path), "leaves": result.get("leaves")},
    )
    print(json.dumps(result, ensure_ascii=False))
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
    append_chapter_parser.add_argument(
        "--lens-heading",
        choices=sorted(_LENS_HEADING_VALUES),
        default="omit",
        help="omit (default): anchor+body only; show: #### title under anchor",
    )

    assemble_parser = sub.add_parser(
        "assemble-arc",
        help="Assemble design doc from narrative-arc tree + chapter bodies",
    )
    assemble_parser.add_argument("--path", type=Path, required=True)
    assemble_parser.add_argument("--revision-dir", type=Path, required=True)
    assemble_parser.add_argument("--preamble", type=str, default=None)
    assemble_parser.add_argument("--preamble-file", type=Path, default=None)
    assemble_parser.add_argument(
        "--lens-heading",
        choices=sorted(_LENS_HEADING_VALUES),
        default="omit",
    )
    assemble_parser.add_argument(
        "--tree",
        choices=sorted(_TREE_MODE_VALUES),
        default="auto",
        help="auto: use tree when present; require: fail without tree; ignore: leaf-flat",
    )
    assemble_parser.add_argument(
        "--skip-write-state",
        action="store_true",
        help="Debug/legacy only: skip chapter write-state complete gate",
    )
    assemble_parser.add_argument(
        "--conversation-id",
        default="",
        help="Conversation id for workflow biz logs (optional)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init-doc":
        return cmd_init_doc(args)
    if args.command == "append-chapter":
        return cmd_append_chapter(args)
    if args.command == "assemble-arc":
        return cmd_assemble_arc(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
