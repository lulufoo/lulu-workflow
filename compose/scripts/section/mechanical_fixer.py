#!/usr/bin/env python3
"""Mechanical fixer: applies deterministic structural fixes to a compose document.

CLI:
    python3 mechanical_fixer.py apply-mechanical-fix \\
        --doc-path <design-doc.md> \\
        --gap-item <gap-item-json-string> \\
        [--dry-run]

Exit codes:
    0   fix applied successfully (or no change needed)
    1   hard error (bad args, file not found, parse failure)
    2   DEGRADE: fixer cannot handle this gap — caller should degrade to kw_subsection
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

from structural_section_utils import (  # noqa: E402
    check_id_from_gap_item,
    replace_line,
    section_header,
)

_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)

_SUPPORTED_FIXER_ACTIONS = frozenset({"insert_anchor", "normalize_heading"})

EXIT_DEGRADE = 2

_FIXER_ACTION_BY_CHECK = {
    "anchor_missing": "insert_anchor",
    "heading_depth": "normalize_heading",
}

_FAILURE_HINTS = ("cannot", "not found", "no suitable", "no anchored", "no header")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _infer_fixer_action(check_id: str) -> str | None:
    return _FIXER_ACTION_BY_CHECK.get(check_id)


def _resolve_fixer_action(gap_item: dict[str, Any]) -> str | None:
    explicit = gap_item.get("fixer_action")
    if explicit:
        return str(explicit)
    check_id = check_id_from_gap_item(gap_item)
    return _infer_fixer_action(check_id) if check_id else None


def _emit_degrade(action: str | None, section_key: str, message: str) -> None:
    result = {
        "action": action or "unknown",
        "section_key": section_key,
        "message": message,
        "degraded": True,
    }
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(EXIT_DEGRADE)


def _apply_insert_anchor(text: str, section_key: str) -> tuple[str, str, bool]:
    key = section_key.strip().upper()
    anchor = f"<!-- section-key:{key} -->"
    header = section_header(text, key)
    if header is None:
        return text, f"section {key} not found — cannot insert anchor", False

    if header.has_anchor and anchor in header.line_text:
        return text, "anchor already correct — no change", True

    if "<!-- section-key:" in header.line_text:
        new_line = _SECTION_KEY_ANCHOR_RE.sub(anchor, header.line_text)
        if new_line == header.line_text:
            new_line = header.line_text.rstrip() + f" {anchor}"
    else:
        new_line = header.line_text.rstrip() + f" {anchor}"

    new_text = replace_line(text, header, new_line)
    return new_text, f"inserted anchor {anchor}", True


def _apply_normalize_heading(
    text: str,
    section_key: str,
    expected_level: int = 2,
) -> tuple[str, str, bool]:
    header = section_header(text, section_key)
    if header is None:
        return text, f"section {section_key} not found — cannot normalize heading", False

    if header.heading_level == expected_level:
        return text, f"heading already H{expected_level} — no change", True

    title = re.sub(r"^#{1,6}\s+", "", header.line_text).strip()
    title = _SECTION_KEY_ANCHOR_RE.sub("", title).strip()
    new_line = f"{'#' * expected_level} {title}"
    if "<!-- section-key:" in header.line_text:
        anchor_match = _SECTION_KEY_ANCHOR_RE.search(header.line_text)
        if anchor_match:
            new_line = f"{new_line} {anchor_match.group(0)}"

    new_text = replace_line(text, header, new_line)
    return new_text, f"normalized heading from H{header.heading_level} to H{expected_level}", True


def _is_fix_failure(message: str, *, changed: bool) -> bool:
    if changed:
        return False
    lowered = message.lower()
    return any(hint in lowered for hint in _FAILURE_HINTS)


def apply_mechanical_fix(
    doc_path: Path,
    gap_item: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the mechanical fix for gap_item to doc_path."""
    section_key = str(gap_item.get("section_key", "")).upper()
    fixer_action = _resolve_fixer_action(gap_item)

    if fixer_action not in _SUPPORTED_FIXER_ACTIONS:
        _emit_degrade(
            fixer_action,
            section_key,
            (
                f"fixer_action {fixer_action!r} is not in the mechanical fixer whitelist "
                f"({', '.join(sorted(_SUPPORTED_FIXER_ACTIONS))}); degrading to kw_subsection"
            ),
        )

    if not doc_path.exists():
        raise ValueError(f"doc-path not found: {doc_path}")

    text = doc_path.read_text(encoding="utf-8")
    expected_level = 2
    if fixer_action == "insert_anchor":
        new_text, message, ok = _apply_insert_anchor(text, section_key)
    else:
        new_text, message, ok = _apply_normalize_heading(text, section_key, expected_level)

    changed = new_text != text
    if not ok or _is_fix_failure(message, changed=changed):
        _emit_degrade(fixer_action, section_key, message)

    if changed and not dry_run:
        _atomic_write(doc_path, new_text)

    return {
        "action": fixer_action,
        "section_key": section_key,
        "message": message + (" (dry-run)" if dry_run and changed else ""),
        "degraded": False,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(description="mechanical fixer for structural compose document gaps")
    subparsers = parser.add_subparsers(dest="subcommand")

    fix_parser = subparsers.add_parser(
        "apply-mechanical-fix",
        help="Apply a mechanical fix for one structural gap item",
    )
    fix_parser.add_argument("--doc-path", type=Path, required=True, help="Path to compose document (.md)")
    fix_parser.add_argument(
        "--gap-item",
        required=True,
        help="Gap item JSON string (from read-gap-item)",
    )
    fix_parser.add_argument("--dry-run", action="store_true", help="Print result without writing to disk")

    args = parser.parse_args()

    if args.subcommand != "apply-mechanical-fix":
        parser.print_help()
        return 1

    try:
        gap_item = json.loads(args.gap_item)
    except json.JSONDecodeError as exc:
        print(f"invalid --gap-item JSON: {exc}", file=sys.stderr)
        return 1

    try:
        result = apply_mechanical_fix(args.doc_path, gap_item, dry_run=args.dry_run)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SystemExit as exc:
        return int(exc.code)

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
