"""Strict, single-target unified-diff parsing and application."""

from __future__ import annotations

from dataclasses import dataclass
import re


_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?: .*)?$",
)


@dataclass(frozen=True)
class Hunk:
    """One position-bound unified-diff hunk."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]


def parse_unified_diff(diff: str) -> list[Hunk]:
    """Parse a conventional unified diff without accepting fuzzy syntax."""
    if not isinstance(diff, str) or not diff:
        raise ValueError("unified_diff must be a non-empty string")

    lines = diff.splitlines()
    hunks: list[Hunk] = []
    index = 0
    if index < len(lines) and lines[index].startswith("--- "):
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise ValueError("unified_diff file header must contain --- and +++ lines")
        index += 2

    while index < len(lines):
        match = _HUNK_HEADER.match(lines[index])
        if not match:
            raise ValueError(f"invalid unified_diff hunk header at line {index + 1}")
        old_start = int(match["old_start"])
        old_count = int(match["old_count"] or "1")
        new_start = int(match["new_start"])
        new_count = int(match["new_count"] or "1")
        index += 1
        hunk_lines: list[str] = []
        old_seen = 0
        new_seen = 0
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if not line or line[0] not in {" ", "+", "-"}:
                raise ValueError(f"invalid unified_diff hunk line at line {index + 1}")
            hunk_lines.append(line)
            if line[0] in {" ", "-"}:
                old_seen += 1
            if line[0] in {" ", "+"}:
                new_seen += 1
            index += 1
        if old_seen != old_count or new_seen != new_count:
            raise ValueError(
                "unified_diff hunk counts do not match hunk body "
                f"(expected -{old_count}/+{new_count}, got -{old_seen}/+{new_seen})",
            )
        hunks.append(
            Hunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=tuple(hunk_lines),
            ),
        )

    if not hunks:
        raise ValueError("unified_diff must contain at least one hunk")
    return hunks


def apply_unified_diff(original: str, diff: str) -> str:
    """Apply only hunks that match their declared original offsets exactly."""
    original_lines = original.splitlines(keepends=True)
    output: list[str] = []
    source_index = 0

    for hunk in parse_unified_diff(diff):
        hunk_start = hunk.old_start - 1 if hunk.old_start else 0
        if hunk_start < source_index or hunk_start > len(original_lines):
            raise ValueError("unified_diff hunk offsets overlap or exceed original content")
        output.extend(original_lines[source_index:hunk_start])
        source_index = hunk_start
        for line in hunk.lines:
            marker, expected = line[0], line[1:]
            if marker in {" ", "-"}:
                if source_index >= len(original_lines):
                    raise ValueError("unified_diff hunk exceeds original content")
                actual = original_lines[source_index]
                if actual.rstrip("\r\n") != expected:
                    raise ValueError(
                        "unified_diff hunk context does not match declared original location",
                    )
                source_index += 1
            if marker in {" ", "+"}:
                output.append(actual if marker == " " else expected + "\n")

    output.extend(original_lines[source_index:])
    return "".join(output)
