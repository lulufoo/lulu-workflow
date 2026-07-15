#!/usr/bin/env python3
"""Split EvalTarget (B) markdown into intent units — K3-d (chapter-only).

Reads **only** the delivered document text. Recognizes B-local anchors:

- ``<!-- chapter:{cid} -->`` (fact-first compose docs)

Does **not** import the compose kernel or read compose revision sidecars.
Section-key grammar retired in K3-d.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

Shape = Literal["chapter", "unknown"]

_CHAPTER_ANCHOR_RE = re.compile(r"<!--\s*chapter:\s*(\S+?)\s*-->", re.IGNORECASE)
_SUBHEADING_RE = re.compile(r"(?m)^(#{2,3})\s+\S")


def detect_shape(text: str) -> Shape:
    """Return which anchor grammar dominates ``text``."""
    if _CHAPTER_ANCHOR_RE.search(text) is not None:
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


def _is_boilerplate_unit(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {"---", "***", "___"}:
        return True
    return False


def split_intent_units(body: str, *, container_id: str) -> list[dict[str, str]]:
    """Split one chapter body into intent units.

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
        lead = body[: matches[0].start()].strip()
        if lead and not _is_boilerplate_unit(lead):
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
          "shape": "chapter"|"unknown",
          "containers": [{"id", "body", "units": [{"id","text","container_id"}]}],
          "empty": bool
        }
    """
    shape = detect_shape(text)
    containers: list[dict[str, Any]] = []

    if shape != "chapter":
        return {"shape": shape, "containers": [], "empty": True}

    for cid, body in iter_chapter_segments(text):
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
        description="Inspect EvalTarget (B) intent units (chapter anchors)"
    )
    parser.add_argument("--path", type=Path, required=True, help="Path to EvalTarget B")
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"not a file: {args.path}", file=sys.stderr)
        return 1
    return cmd_inspect(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
