#!/usr/bin/env python3
"""Authoritative read helpers for tech-plan revision{N}/tech-doc.md presentation.

Section bodies are located by `<!-- section-key:KEY -->` anchors (preferred):
either on the H2 line (legacy 10-H2) or inside outline blocks (feature 5-H2).
Legacy registry heading match is a final fallback.

CLI:
    python3 tech_doc_schema.py --schema
    python3 tech_doc_schema.py --read  --path <tech-doc.md>
    python3 tech_doc_schema.py --read  --cycle-id <id> --project-root .
    python3 tech_doc_schema.py --section-body --path <tech-doc.md> --section KEY
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from session_state_schema import load_active_doc_from_cycle
from section_registry_schema import section_heading, summary_section_key
from workflow_common import read_md_field, tech_doc_path

_SCHEMA: list[dict] = [
    {"field": "path", "type": "string", "required": True,
     "description": "Absolute path to revision{N}/tech-doc.md"},
    {"field": "revision", "type": "integer", "required": True,
     "description": "Active document round from session-state.md"},
    {"field": "title", "type": "string", "required": True,
     "description": "First H1 heading, or lead line from summary section"},
    {"field": "summary", "type": "string", "required": True,
     "description": "Summary section body (registry summary_section_key), truncated"},
]
_SUMMARY_MAX_LEN = 300

_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)
_SECTION_HEADER_WITH_KEY_RE = re.compile(
    r"^##\s+(.*?)\s*<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_H2_RE = re.compile(r"^##\s+", re.MULTILINE)


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


def _section_body_by_heading(text: str, heading: str) -> str:
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


def format_section_heading(section_key: str, display_title: str) -> str:
    """Return H2 line with stable section-key anchor for tech-doc writers."""
    key = section_key.strip().upper()
    title = display_title.strip() or "（待命名）"
    return f"## {title} <!-- section-key:{key} -->"


def format_section_intent_anchor(section_key: str) -> str:
    """Return intent anchor comment for outline-block assembly."""
    key = section_key.strip().upper()
    return f"<!-- section-key:{key} -->"


def _next_boundary(body: str, start: int, anchor_positions: list[int]) -> int:
    """Return end offset for section body starting at start."""
    next_h2 = _H2_RE.search(body, start)
    h2_pos = next_h2.start() if next_h2 else len(body)
    later_anchors = [pos for pos in anchor_positions if pos > start]
    anchor_pos = later_anchors[0] if later_anchors else len(body)
    return min(h2_pos, anchor_pos)


def _parse_sections_by_intent_anchors(
    body: str,
) -> dict[str, dict[str, str]]:
    """Parse intent-key bodies from standalone section-key anchors."""
    sections: dict[str, dict[str, str]] = {}
    anchor_matches = list(_SECTION_KEY_ANCHOR_RE.finditer(body))
    if not anchor_matches:
        return sections

    anchor_positions = [match.start() for match in anchor_matches]
    for index, match in enumerate(anchor_matches):
        key = match.group(1).upper()
        line_start = body.rfind("\n", 0, match.start()) + 1
        line_end = body.find("\n", match.start())
        if line_end == -1:
            line_end = len(body)
        line = body[line_start:line_end]
        h2_match = _SECTION_HEADER_WITH_KEY_RE.match(line)
        if h2_match:
            display = h2_match.group(1).strip()
            start = match.end()
        else:
            display = ""
            start = match.end()
        end = _next_boundary(body, start, anchor_positions)
        sections[key] = {
            "display_heading": display,
            "body": body[start:end].strip(),
        }
    return sections


def parse_sections(
    text: str,
    *,
    project_root: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Parse tech-doc into section_key → {display_heading, body}."""
    body = _strip_frontmatter(text)
    sections = _parse_sections_by_intent_anchors(body)
    if sections:
        return sections

    matches = list(_SECTION_HEADER_WITH_KEY_RE.finditer(body))
    for index, match in enumerate(matches):
        key = match.group(2).upper()
        display = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[key] = {
            "display_heading": display,
            "body": body[start:end].strip(),
        }

    if sections:
        return sections

    from section_registry_schema import section_order  # noqa: WPS433

    for key in section_order(project_root):
        heading = section_heading(key, project_root=project_root)
        legacy_body = _section_body_by_heading(body, heading)
        if legacy_body or heading:
            sections[key] = {
                "display_heading": heading,
                "body": legacy_body,
            }
    return sections


def section_display_heading(
    text: str,
    section_key: str,
    *,
    project_root: Path | None = None,
) -> str:
    """Return human display title for a section (from anchor or registry fallback)."""
    key = section_key.strip().upper()
    parsed = parse_sections(text, project_root=project_root)
    if key in parsed:
        return parsed[key]["display_heading"]
    return section_heading(key, project_root=project_root)


def section_body_by_key(
    text: str,
    section_key: str,
    *,
    project_root: Path | None = None,
) -> str:
    """Return section body located by section-key anchor or legacy heading."""
    key = section_key.strip().upper()
    parsed = parse_sections(text, project_root=project_root)
    if key in parsed:
        return parsed[key]["body"]
    body = _strip_frontmatter(text)
    return _section_body_by_heading(body, section_heading(key, project_root=project_root))


def extract_presentation(path: Path, *, revision: int | None = None) -> dict:
    """Read tech-doc.md and return path/title/summary presentation fields."""
    if not path.exists():
        raise ValueError(f"tech-doc.md not found: {path}")

    raw = path.read_text(encoding="utf-8")
    body = _strip_frontmatter(raw)
    summary_key = summary_section_key()
    summary_body = section_body_by_key(raw, summary_key)

    title = _first_h1(body)
    if not title:
        title = _first_content_line(summary_body)
    if not title:
        title = f"revision{revision} tech-doc" if revision is not None else path.stem

    summary = _truncate_summary(summary_body)

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
    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
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
    parser.add_argument("--section-body", action="store_true", help="Print section body JSON")
    parser.add_argument("--path", type=Path, help="Path to tech-doc.md")
    parser.add_argument("--section", type=str, help="Section key for --section-body")
    parser.add_argument("--cycle-id", type=str, help="Cycle ID for --read")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    project_root = args.project_root.resolve()

    if args.section_body:
        if not args.path or not args.section:
            parser.error("--section-body requires --path and --section")
        raw = args.path.resolve().read_text(encoding="utf-8")
        key = args.section.strip().upper()
        body = section_body_by_key(raw, key, project_root=project_root)
        payload = {
            "section_key": key,
            "display_heading": section_display_heading(raw, key, project_root=project_root),
            "body": body,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.read:
        try:
            if args.cycle_id:
                data = load_presentation_from_cycle(
                    args.cycle_id.strip(),
                    project_root,
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
