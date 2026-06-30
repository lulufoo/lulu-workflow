#!/usr/bin/env python3
"""Structural probe: deterministic structural validation of a compose document section.

CLI:
    python3 structural_probe.py \\
        --doc-path <design-doc.md> \\
        --section <SECTION_KEY> \\
        --criteria <structural-probe-criteria.json> \\
        [--profile <profile-id>]

Subcommands (default: run):
    run         Run all enabled checks for the given section (default, no positional arg needed)
    list-checks Print enabled check ids from criteria JSON

Outputs a JSON object:
    {
        "section_key": "IF",
        "items": [<gap_kind=structural item>, ...]
    }

Exit codes:
    0  success (gaps found or not — check items[] length)
    1  error (bad args, missing file, etc.)
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

from compose_doc_schema import parse_sections, section_body_by_key  # noqa: E402
from probe_report_schema import infer_fix_mode, infer_repair_class  # noqa: E402
from section_registry_schema import section_keys as _registry_section_keys  # noqa: E402
from structural_section_utils import (  # noqa: E402
    section_anchor_present,
    section_header,
)


def _load_criteria(criteria_path: Path) -> list[dict[str, Any]]:
    data = json.loads(criteria_path.read_text(encoding="utf-8"))
    return [c for c in data.get("checks", []) if c.get("enabled", True)]


def _make_item(
    *,
    check: dict[str, Any],
    section_key: str,
    section: str,
    scope: str,
    intent_gap: str,
    subsection_title: str = "",
) -> dict[str, Any]:
    check_id = str(check.get("check_id", ""))
    gap_kind = "structural"
    repair_class = infer_repair_class(gap_kind)
    fix_mode = infer_fix_mode(repair_class)
    slug = (
        re.sub(r"[^a-z0-9_]+", "_", subsection_title.lower()).strip("_")[:40]
        if subsection_title
        else ""
    )
    item_id = f"{section_key}-S-{check_id}" + (f"-{slug}" if slug else "")
    fixer_action = check.get("fixer_action")
    return {
        "id": item_id,
        "check_id": check_id,
        "gap_kind": gap_kind,
        "repair_class": repair_class,
        "fix_mode": fix_mode,
        "fixer_action": fixer_action,
        "handled_by": None,
        "degraded_from": None,
        "scope": scope,
        "section_key": section_key,
        "section": section,
        "sub_section_summary": f"{section_key}: {intent_gap[:80]}",
        "sub_section_text": "",
        "skip_key": f"{section_key}:structural:{check_id}" + (f":{slug}" if slug else ""),
        "intent_gap": intent_gap,
        "target_kw": None,
        "kw_criteria": None,
        "upstream_section": None,
        "upstream_relation": None,
        "upstream_criteria": None,
        "intent_criteria": None,
        "status": "open",
        "decision": "—",
    }


def _format_intent_gap(check: dict[str, Any], **fields: str) -> str:
    template = check.get("intent_gap_template", "")
    if template:
        return template.format(**fields)
    return ""


def _check_anchor_missing(
    doc_text: str,
    section_key: str,
    section: str,
    check: dict[str, Any],
) -> list[dict[str, Any]]:
    if section_header(doc_text, section_key) is None and not section_body_by_key(
        doc_text, section_key
    ).strip():
        return []
    if section_anchor_present(doc_text, section_key):
        return []
    intent_gap = _format_intent_gap(check, section_key=section_key) or (
        f"Section {section_key} is missing its <!-- section-key:{section_key} --> anchor comment."
    )
    return [
        _make_item(
            check=check,
            section_key=section_key,
            section=section,
            scope="section",
            intent_gap=intent_gap,
        )
    ]


def _check_heading_depth(
    doc_text: str,
    section_key: str,
    section: str,
    check: dict[str, Any],
) -> list[dict[str, Any]]:
    header = section_header(doc_text, section_key)
    if header is None:
        return []
    config = check.get("config", {})
    expected_level = int(config.get("section_heading_level", 2))
    if header.heading_level == expected_level:
        return []
    intent_gap = _format_intent_gap(
        check,
        section_key=section_key,
        observed_level=f"H{header.heading_level}",
        expected_level=f"H{expected_level}",
    ) or (
        f"Section {section_key} heading is H{header.heading_level}, expected H{expected_level}."
    )
    return [
        _make_item(
            check=check,
            section_key=section_key,
            section=section,
            scope="section",
            intent_gap=intent_gap,
        )
    ]


def _check_required_subsection_missing(
    body: str,
    section_key: str,
    section: str,
    check: dict[str, Any],
) -> list[dict[str, Any]]:
    required_subsections: list[str] = check.get("required_subsections") or []
    items = []
    for title in required_subsections:
        pattern = re.compile(
            r"^###\s+" + re.escape(title),
            re.IGNORECASE | re.MULTILINE,
        )
        if pattern.search(body):
            continue
        intent_gap = _format_intent_gap(
            check, subsection_title=title, section_key=section_key
        ) or (f"Required sub-section '{title}' is missing from section {section_key}.")
        items.append(
            _make_item(
                check=check,
                section_key=section_key,
                section=section,
                scope="subsection",
                intent_gap=intent_gap,
                subsection_title=title,
            )
        )
    return items


def _line_is_placeholder(line: str, compiled: list[re.Pattern[str]]) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in compiled)


def _check_placeholder_remaining(
    body: str,
    section_key: str,
    section: str,
    check: dict[str, Any],
) -> list[dict[str, Any]]:
    placeholder_patterns: list[str] = check.get(
        "placeholder_patterns",
        [r"^\s*TODO\s*$", r"^\s*TBD\s*$", r"<!--\s*TODO[^>]*-->", r"^\s*\(placeholder\)\s*$"],
    )
    compiled = [re.compile(p, re.IGNORECASE) for p in placeholder_patterns]

    h3_pattern = re.compile(r"^###\s+(.+?)(?:\s*<!--[^>]*-->)?\s*$", re.MULTILINE)
    h3_boundaries = [(m.start(), m.group(1).strip()) for m in h3_pattern.finditer(body)]

    items = []
    for i, (start, title) in enumerate(h3_boundaries):
        end = h3_boundaries[i + 1][0] if i + 1 < len(h3_boundaries) else len(body)
        sub_body = body[start:end]
        content_lines = [
            line
            for line in sub_body.splitlines()
            if line.strip() and not line.strip().startswith("###")
        ]
        if not content_lines:
            continue
        if not all(_line_is_placeholder(line, compiled) for line in content_lines):
            continue
        intent_gap = _format_intent_gap(
            check, subsection_title=title, section_key=section_key
        ) or (
            f"Sub-section '{title}' in {section_key} contains only a placeholder "
            "and has not been filled in."
        )
        items.append(
            _make_item(
                check=check,
                section_key=section_key,
                section=section,
                scope="subsection",
                intent_gap=intent_gap,
                subsection_title=title,
            )
        )
    return items


_CHECK_HANDLERS = {
    "anchor_missing": lambda doc, body, key, section, check: _check_anchor_missing(
        doc, key, section, check
    ),
    "heading_depth": lambda doc, body, key, section, check: _check_heading_depth(
        doc, key, section, check
    ),
    "required_subsection_missing": lambda doc, body, key, section, check: _check_required_subsection_missing(
        body, key, section, check
    ),
    "placeholder_remaining": lambda doc, body, key, section, check: _check_placeholder_remaining(
        body, key, section, check
    ),
}


def run_structural_probe(
    doc_path: Path,
    section_key: str,
    criteria_path: Path,
) -> dict[str, Any]:
    """Run all enabled structural checks for section_key. Return items dict."""
    key = section_key.strip().upper()
    if key not in _registry_section_keys():
        raise ValueError(f"unknown section_key: {key!r}")

    doc_text = doc_path.read_text(encoding="utf-8")
    parsed = parse_sections(doc_text)
    header = section_header(doc_text, key)
    body = section_body_by_key(doc_text, key)
    if header is None and not body.strip():
        return {"section_key": key, "items": []}

    section = (
        parsed[key].get("display_heading")
        if key in parsed
        else (header.line_text.lstrip("#").split("<!--")[0].strip() if header else key)
    ) or key
    checks = _load_criteria(criteria_path)
    items: list[dict[str, Any]] = []

    for check in checks:
        check_id = check.get("check_id", "")
        handler = _CHECK_HANDLERS.get(check_id)
        if handler is None:
            continue
        try:
            found = handler(doc_text, body, key, section, check)
        except Exception as exc:  # noqa: BLE001
            print(f"structural_probe: check {check_id!r} failed: {exc}", file=sys.stderr)
            continue
        items.extend(found)

    return {"section_key": key, "items": items}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="structural probe for compose document section")
    parser.add_argument("subcommand", nargs="?", default="run", choices=["run", "list-checks"])
    parser.add_argument("--doc-path", type=Path, help="Path to compose document (.md)")
    parser.add_argument("--section", help="Section key to probe (e.g. IF)")
    parser.add_argument("--criteria", type=Path, help="Path to structural-probe-criteria.json")
    parser.add_argument("--profile", default=None, help="Profile id (informational only)")
    args = parser.parse_args()

    if args.subcommand == "list-checks":
        if not args.criteria or not args.criteria.exists():
            print("--criteria required for list-checks", file=sys.stderr)
            return 1
        checks = _load_criteria(args.criteria)
        print(json.dumps([c.get("check_id") for c in checks], ensure_ascii=False, indent=2))
        return 0

    for required, name in [(args.doc_path, "--doc-path"), (args.section, "--section"), (args.criteria, "--criteria")]:
        if not required:
            print(f"{name} is required", file=sys.stderr)
            return 1

    if not args.doc_path.exists():
        print(f"doc-path not found: {args.doc_path}", file=sys.stderr)
        return 1
    if not args.criteria.exists():
        print(f"criteria not found: {args.criteria}", file=sys.stderr)
        return 1

    try:
        result = run_structural_probe(args.doc_path, args.section, args.criteria)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
