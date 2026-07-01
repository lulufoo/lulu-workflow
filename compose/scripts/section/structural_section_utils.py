"""Shared section header/anchor helpers for structural probe and mechanical fixer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from compose_doc_schema import parse_sections  # noqa: E402
from section_registry_schema import section_heading  # noqa: E402

_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)
_SECTION_HEADER_WITH_KEY_RE = re.compile(
    r"^(#{1,6})\s+(.*?)\s*<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class SectionHeader:
    """Located section header in a compose document."""

    section_key: str
    heading_level: int
    line_start: int
    line_end: int
    line_text: str
    has_anchor: bool


def strip_frontmatter(text: str) -> str:
    body, _offset = strip_frontmatter_with_offset(text)
    return body


def strip_frontmatter_with_offset(text: str) -> tuple[str, int]:
    if not text.startswith("---"):
        return text, 0
    end = text.find("---", 3)
    if end == -1:
        return text, 0
    offset = end + 3
    if offset < len(text) and text[offset] == "\n":
        offset += 1
    return text[offset:], offset


def section_header(text: str, section_key: str) -> SectionHeader | None:
    """Return header metadata for section_key, or None if the section is absent."""
    key = section_key.strip().upper()
    body, body_offset = strip_frontmatter_with_offset(text)
    parsed = parse_sections(text)

    def _with_offset(header: SectionHeader) -> SectionHeader:
        return SectionHeader(
            section_key=header.section_key,
            heading_level=header.heading_level,
            line_start=header.line_start + body_offset,
            line_end=header.line_end + body_offset,
            line_text=header.line_text,
            has_anchor=header.has_anchor,
        )

    for match in _SECTION_HEADER_WITH_KEY_RE.finditer(body):
        if match.group(3).upper() != key:
            continue
        return _with_offset(
            SectionHeader(
                section_key=key,
                heading_level=len(match.group(1)),
                line_start=match.start(),
                line_end=match.end(),
                line_text=match.group(0),
                has_anchor=True,
            )
        )

    for match in _SECTION_KEY_ANCHOR_RE.finditer(body):
        if match.group(1).upper() != key:
            continue
        line_start = body.rfind("\n", 0, match.start()) + 1
        line_end = body.find("\n", match.end())
        if line_end == -1:
            line_end = len(body)
        line = body[line_start:line_end]
        header_match = _HEADING_LINE_RE.match(line.strip())
        if header_match and "<!--" not in header_match.group(2):
            return _with_offset(
                SectionHeader(
                    section_key=key,
                    heading_level=len(header_match.group(1)),
                    line_start=line_start,
                    line_end=line_end,
                    line_text=line,
                    has_anchor=True,
                )
            )
        prev = body[:line_start].rstrip("\n")
        if prev:
            prev_line = prev.rsplit("\n", 1)[-1]
            prev_match = _HEADING_LINE_RE.match(prev_line.strip())
            if prev_match:
                prev_start = line_start - len(prev_line)
                if prev_start > 0 and body[prev_start - 1] == "\n":
                    prev_start -= 1
                return _with_offset(
                    SectionHeader(
                        section_key=key,
                        heading_level=len(prev_match.group(1)),
                        line_start=max(0, prev_start),
                        line_end=line_end,
                        line_text=prev_line,
                        has_anchor=True,
                    )
                )

    display = parsed[key].get("display_heading", "").strip() if key in parsed else ""
    if not display:
        display = section_heading(key).strip()
    if display:
        pattern = re.compile(
            rf"^(#{{1,6}})\s+{re.escape(display)}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        legacy = pattern.search(body)
        if legacy:
            return _with_offset(
                SectionHeader(
                    section_key=key,
                    heading_level=len(legacy.group(1)),
                    line_start=legacy.start(),
                    line_end=legacy.end(),
                    line_text=legacy.group(0),
                    has_anchor=False,
                )
            )
    return None


def section_anchor_present(text: str, section_key: str) -> bool:
    key = section_key.strip().upper()
    body = strip_frontmatter(text)
    return any(match.group(1).upper() == key for match in _SECTION_KEY_ANCHOR_RE.finditer(body))


def replace_line(text: str, header: SectionHeader, new_line: str) -> str:
    return text[: header.line_start] + new_line + text[header.line_end :]


def check_id_from_gap_item(gap_item: dict[str, Any]) -> str:
    explicit = str(gap_item.get("check_id", "")).strip()
    if explicit:
        return explicit
    skip_key = str(gap_item.get("skip_key", ""))
    parts = skip_key.split(":")
    if len(parts) >= 3 and parts[1] == "structural":
        return parts[2]
    item_id = str(gap_item.get("id", ""))
    if "-S-" in item_id:
        return item_id.split("-S-", 1)[1]
    return ""
