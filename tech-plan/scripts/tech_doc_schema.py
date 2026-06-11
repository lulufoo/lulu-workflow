#!/usr/bin/env python3
"""Authoritative read helpers for tech-plan revision{N}/tech-doc.md presentation.

CLI:
    python3 tech_doc_schema.py --schema
    python3 tech_doc_schema.py --read  --path <tech-doc.md>
    python3 tech_doc_schema.py --read  --cycle-id <id> --project-root .
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from workflow_common import read_md_field, session_base_dir, tech_doc_path

_SCHEMA: list[dict] = [
    {"field": "path", "type": "string", "required": True,
     "description": "Absolute path to revision{N}/tech-doc.md"},
    {"field": "revision", "type": "integer", "required": True,
     "description": "Active document round from session-state.md"},
    {"field": "title", "type": "string", "required": True,
     "description": "First H1 heading, or North Star lead line"},
    {"field": "summary", "type": "string", "required": True,
     "description": "North Star section body, whitespace-collapsed, truncated"},
]

_NORTH_STAR_HEADING = "North Star"
_SUMMARY_MAX_LEN = 300


def get_schema() -> list[dict]:
    """Return field definitions for tech-doc presentation payload."""
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


def _section_body(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


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


def extract_presentation(path: Path, *, revision: int | None = None) -> dict:
    """Read tech-doc.md and return path/title/summary presentation fields."""
    if not path.exists():
        raise ValueError(f"tech-doc.md not found: {path}")

    body = _strip_frontmatter(path.read_text(encoding="utf-8"))
    north_star = _section_body(body, _NORTH_STAR_HEADING)

    title = _first_h1(body)
    if not title:
        title = _first_content_line(north_star)
    if not title:
        title = f"revision{revision} tech-doc" if revision is not None else path.stem

    summary = _truncate_summary(north_star)

    payload: dict = {
        "path": str(path.resolve()),
        "title": title,
        "summary": summary,
    }
    if revision is not None:
        payload["revision"] = revision
    return payload


def resolve_tech_doc_path_from_cycle(cycle_id: str, project_root: Path) -> tuple[Path, int]:
    """Resolve revision{N}/tech-doc.md via session-state.md active_doc."""
    ss_path = project_root / session_base_dir(cycle_id) / "session-state.md"
    try:
        active_doc = int(read_md_field(ss_path, "active_doc", default="1"))
    except ValueError:
        active_doc = 1
    return project_root / tech_doc_path(cycle_id, active_doc), active_doc


def load_presentation_from_cycle(cycle_id: str, project_root: Path) -> dict:
    """Resolve active tech-doc and return presentation payload."""
    path, revision = resolve_tech_doc_path_from_cycle(cycle_id, project_root)
    payload = extract_presentation(path, revision=revision)
    payload["revision"] = revision
    return payload


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan tech-doc.md presentation utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    parser.add_argument("--read", action="store_true", help="Print presentation payload as JSON")
    parser.add_argument("--path", type=Path, help="Path to tech-doc.md")
    parser.add_argument("--cycle-id", type=str, help="Cycle ID for --read")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if args.read:
        try:
            if args.cycle_id:
                data = load_presentation_from_cycle(
                    args.cycle_id.strip(),
                    args.project_root.resolve(),
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
    sys.exit(_cli())
