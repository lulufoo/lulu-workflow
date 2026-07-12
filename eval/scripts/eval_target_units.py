#!/usr/bin/env python3
"""Split EvalTarget (B) markdown into intent units — K3-c / M4b (option 1).

Reads **only** the delivered document text. Recognizes B-local anchors:

- ``<!-- chapter:{cid} -->`` (display_layer docs)
- ``<!-- section-key:K -->`` (legacy section-keyed docs)

Does **not** import the compose kernel or read compose revision sidecars.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

Shape = Literal["chapter", "section-key", "unknown"]

_CHAPTER_ANCHOR_RE = re.compile(r"<!--\s*chapter:\s*(\S+?)\s*-->", re.IGNORECASE)
_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)
_SUBHEADING_RE = re.compile(r"(?m)^(#{2,3})\s+\S")


def detect_shape(text: str) -> Shape:
    """Return which anchor grammar dominates ``text``."""
    has_chapter = _CHAPTER_ANCHOR_RE.search(text) is not None
    has_section = _SECTION_KEY_ANCHOR_RE.search(text) is not None
    if has_chapter and not has_section:
        return "chapter"
    if has_section and not has_chapter:
        return "section-key"
    if has_chapter and has_section:
        # Malformed mix — prefer chapter (current display_layer writers never mix).
        return "chapter"
    return "unknown"


def iter_chapter_segments(text: str) -> list[tuple[str, str]]:
    """Return ``(cid, body)`` segments in document order."""
    matches = list(_CHAPTER_ANCHOR_RE.finditer(text))
    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        cid = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segments.append((cid, text[start:end].strip()))
    return segments


def iter_section_key_segments(text: str) -> list[tuple[str, str]]:
    """Return ``(KEY, body)`` segments in document order (legacy B)."""
    matches = list(_SECTION_KEY_ANCHOR_RE.finditer(text))
    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        key = match.group(1).strip().upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        # Drop trailing content up to next anchor; strip outer whitespace.
        body = text[start:end].strip()
        segments.append((key, body))
    return segments


def _is_boilerplate_unit(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    # Single horizontal rule / empty table spacer
    if stripped in {"---", "***", "___"}:
        return True
    return False


def split_intent_units(body: str, *, container_id: str) -> list[dict[str, str]]:
    """Split one chapter/section body into intent units.

    Preference: ``##`` / ``###`` sub-blocks. If none, the whole non-empty body
    is one unit. Skips empty / boilerplate-only slices.
    """
    body = body.strip()
    if not body:
        return []

    matches = list(_SUBHEADING_RE.finditer(body))
    chunks: list[str] = []
    if not matches:
        chunks = [body]
    else:
        # Lead-in before first subheading (often the chapter H2) — keep if
        # it has prose beyond a single heading line.
        lead = body[: matches[0].start()].strip()
        if lead and not _is_boilerplate_unit(lead):
            # If lead is only one heading line, still keep as context unit.
            chunks.append(lead)
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            chunk = body[start:end].strip()
            if chunk and not _is_boilerplate_unit(chunk):
                chunks.append(chunk)

    units: list[dict[str, str]] = []
    for i, chunk in enumerate(chunks, start=1):
        if _is_boilerplate_unit(chunk):
            continue
        units.append(
            {
                "id": f"{container_id}#{i}",
                "text": chunk,
                "container_id": container_id,
            }
        )
    return units


def units_from_eval_target(text: str) -> dict[str, Any]:
    """Build a probe-oriented view of B.

    Returns::

        {
          "shape": "chapter"|"section-key"|"unknown",
          "containers": [{"id", "body", "units": [{"id","text","container_id"}]}],
          "empty": bool
        }
    """
    shape = detect_shape(text)
    containers: list[dict[str, Any]] = []

    if shape == "chapter":
        segments = iter_chapter_segments(text)
    elif shape == "section-key":
        segments = iter_section_key_segments(text)
    else:
        return {"shape": shape, "containers": [], "empty": True}

    for cid, body in segments:
        units = split_intent_units(body, container_id=cid)
        containers.append({"id": cid, "body": body, "units": units})

    empty = not any(c["units"] for c in containers)
    return {"shape": shape, "containers": containers, "empty": empty}


def prior_container_units(
    view: dict[str, Any], container_id: str
) -> list[dict[str, str]]:
    """All units from containers strictly before ``container_id`` (doc order)."""
    prior: list[dict[str, str]] = []
    for container in view.get("containers", []):
        if container["id"] == container_id:
            break
        prior.extend(container["units"])
    return prior


def severity_hints_chapter(view: dict[str, Any], container_id: str) -> dict[str, Any]:
    """Map chapter-path positions to the old section_order severity skeleton.

    | Old (section_order)              | Chapter-path equivalent                          |
    |----------------------------------|--------------------------------------------------|
    | first key                        | first container                                  |
    | last key                         | last container                                   |
    | key has non-empty upstream       | container index > 0 (has prior chapters)         |
    | before last key                  | not last container                               |
    """
    ids = [c["id"] for c in view.get("containers", [])]
    if not ids or container_id not in ids:
        return {
            "is_first": False,
            "is_last": False,
            "has_prior": False,
            "before_last": False,
        }
    index = ids.index(container_id)
    return {
        "is_first": index == 0,
        "is_last": index == len(ids) - 1,
        "has_prior": index > 0,
        "before_last": index < len(ids) - 1,
    }


def cmd_inspect(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    view = units_from_eval_target(text)
    print(json.dumps(view, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect EvalTarget (B) intent units (chapter / section-key)"
    )
    parser.add_argument("--path", type=Path, required=True, help="Path to EvalTarget B")
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"not a file: {args.path}", file=sys.stderr)
        return 1
    return cmd_inspect(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
