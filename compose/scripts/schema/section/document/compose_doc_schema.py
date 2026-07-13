#!/usr/bin/env python3
"""Authoritative read helpers for profile compose documents (presentation).

Compose documents use chapter anchors (``<!-- chapter:{cid} -->``). Section-key
grammar retired in K3-d.

CLI:
    python3 compose_doc_schema.py --schema
    python3 compose_doc_schema.py --read  --path <compose-doc.md>
    python3 compose_doc_schema.py --read  --cycle-id <id> --project-root . [--profile <profile_id>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from chapter_doc_schema import parse_chapter_bodies  # noqa: E402
from session_state_schema import load_active_doc
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import document_path, session_state_path

_SCHEMA: list[dict] = [
    {"field": "path", "type": "string", "required": True,
     "description": "Absolute path to revision{N} compose document"},
    {"field": "revision", "type": "integer", "required": True,
     "description": "Active document round from session-state.md"},
    {"field": "title", "type": "string", "required": True,
     "description": "First H1 heading, or lead line from first chapter / body"},
    {"field": "summary", "type": "string", "required": True,
     "description": "First chapter body (or whole-doc lead), truncated"},
]
_SUMMARY_MAX_LEN = 300


def get_schema() -> list[dict]:
    """Return field definitions for compose document presentation payload."""
    return list(_SCHEMA)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3 :].lstrip("\n")


def _first_h1(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def _first_content_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("<!--"):
            continue
        return stripped
    return ""


def _truncate_summary(text: str, *, max_len: int = _SUMMARY_MAX_LEN) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed:
        return ""
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1] + "…"


def _summary_source(raw: str, body: str) -> str:
    """Prefer first chapter body (document order); else whole body."""
    chapters = parse_chapter_bodies(raw)
    if chapters:
        for segment in chapters.values():
            if segment.strip():
                return segment
    return body


def extract_presentation(path: Path, *, revision: int | None = None) -> dict:
    """Read compose document and return path/title/summary presentation fields."""
    if not path.exists():
        raise ValueError(f"compose document not found: {path}")

    raw = path.read_text(encoding="utf-8")
    body = _strip_frontmatter(raw)
    summary_body = _summary_source(raw, body)

    title = _first_h1(body)
    if not title:
        title = _first_content_line(summary_body)
    if not title:
        title = f"revision{revision} {path.name}" if revision is not None else path.stem

    summary = _truncate_summary(summary_body)

    payload: dict = {
        "path": str(path.resolve()),
        "title": title,
        "summary": summary,
    }
    if revision is not None:
        payload["revision"] = revision
    return payload


def resolve_compose_doc_path_from_cycle(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> tuple[Path, int]:
    """Resolve revision compose document via session-state.md active_doc."""
    active_doc = load_active_doc(
        project_root / session_state_path(cycle_id, profile_id, project_root),
        default=1,
    )
    return project_root / document_path(cycle_id, active_doc, profile_id, project_root), active_doc


def load_presentation_from_cycle(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict:
    """Resolve active compose document and return presentation payload."""
    path, revision = resolve_compose_doc_path_from_cycle(
        cycle_id,
        project_root,
        profile_id=profile_id,
    )
    payload = extract_presentation(path, revision=revision)
    payload["revision"] = revision
    return payload


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Compose document presentation utilities",
    )
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    parser.add_argument("--read", action="store_true", help="Print presentation payload as JSON")
    parser.add_argument("--path", type=Path, help="Path to compose document markdown")
    parser.add_argument("--cycle-id", type=str, help="Cycle ID for --read")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root")
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile / stage name (default: lulu-plan)",
    )
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    project_root = args.project_root.resolve()
    profile_id = args.profile.strip() or DEFAULT_COMPOSE_PROFILE_ID

    if args.read:
        try:
            if args.cycle_id:
                data = load_presentation_from_cycle(
                    args.cycle_id.strip(),
                    project_root,
                    profile_id=profile_id,
                )
            elif args.path:
                data = extract_presentation(args.path.resolve())
            else:
                parser.error("--read requires --path or --cycle-id")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
