#!/usr/bin/env python3
"""Validate Initializing display-layer artifacts and compose document seed.

Subcommands:
    validate    Check revision-dir facts/chapters/derive/body and compose doc

CLI details: ``python3 init_compose_validation.py --help``
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

from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402
from chapter_doc_schema import chapter_anchor_present, chapter_body_by_id  # noqa: E402
from chapters_schema import chapters_path, load_chapters  # noqa: E402
from display_layer_gates import run_display_layer_gates  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from outline_registry_schema import normalize_outline_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    dependency_graph_subset,
    normalize_section_registry,
)
from pd_derivation import normalize_dependency_graph  # noqa: E402


def section_order_for_profile(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    return [str(key).upper() for key in data.get("section_order") or []]


def section_presence_map_for_profile(project_root: Path, profile_id: str) -> dict[str, str]:
    """section_key -> presence ('required'|'optional', default 'required').

    Mirrors ``section_registry_schema.section_presence_map`` but fetches by
    explicit ``profile_id`` rather than the active-session-cached accessor,
    since this validator is invoked with an explicit ``--profile`` flag.
    Feeds ``display_layer_gates.check_c1``.
    """
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    sections = data.get("sections") or {}
    result: dict[str, str] = {}
    for key, val in sections.items():
        presence = (val or {}).get("presence")
        if presence not in ("required", "optional"):
            presence = "required"
        result[str(key).upper()] = presence
    return result


def dependency_graph_for_profile(project_root: Path, profile_id: str) -> dict[str, Any]:
    """Dependency-graph subset for C1 derivation-vs-true-gap classification (K1)."""
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    normalized = normalize_section_registry(data)
    return normalize_dependency_graph(dependency_graph_subset(normalized))


def outline_registry_for_profile(
    project_root: Path,
    profile_id: str,
) -> dict[str, Any] | None:
    try:
        raw = fetch_compose_framework(
            "outline-registry",
            project_root,
            profile_id=profile_id,
        )
    except Exception:
        return None
    return normalize_outline_registry(json.loads(raw))


def validate_display_layer_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None — fact-first P3 validation.

    Validates the fact-first artifact set:

    1. candidates-shaped outline pairing (required);
    2. ``_facts.json`` / ``_chapters.json`` existence + schema-valid;
    3. M2 placement/coverage gates via ``display_layer_gates``;
    4. chapter-artifact existence (non-drop chapter has non-empty
       ``_body-{cid}.txt`` + ``_derive-{cid}.json`` with a ``display_title``);
    5. assembly completeness: every non-drop chapter's anchor is present
       in the compose document with a non-empty segment.
    """
    errors: list[str] = []

    outline = outline_registry_for_profile(project_root, profile_id)
    if outline is None:
        return "failed to fetch/parse outline-registry for this profile"
    if not outline.get("candidates"):
        return (
            "fact-first Init requires a non-empty candidates-shaped outline-registry "
            "(legacy outline_order/blocks, or an empty/null candidates list, is incompatible; "
            "design SSOT §11.4 Major#6)"
        )
    candidate_id_list = [
        str(candidate.get("block", "")).strip() for candidate in outline.get("candidates") or []
    ]

    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return f"invalid or missing _facts.json: {exc}"

    try:
        chapters = load_chapters(chapters_path(revision_dir))
    except ValueError as exc:
        return f"invalid or missing _chapters.json: {exc}"

    presence_map = section_presence_map_for_profile(project_root, profile_id)
    section_order = section_order_for_profile(project_root, profile_id)
    dependency_graph = dependency_graph_for_profile(project_root, profile_id)

    gate_result = run_display_layer_gates(
        facts,
        chapters,
        presence_map=presence_map,
        section_order=section_order,
        candidate_ids=candidate_id_list,
        dependency_graph=dependency_graph,
    )
    errors.extend(gate_result["errors"])

    raw_doc = compose_doc.read_text(encoding="utf-8")
    for chapter in chapters:
        if chapter.get("op") == "drop":
            continue
        cid = str(chapter.get("id", "")).strip()

        derive_file = chapter_derive_path(revision_dir, cid)
        if not derive_file.is_file():
            errors.append(f"chapter {cid!r}: missing {derive_file.name}")
        else:
            try:
                derive_data = json.loads(derive_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"chapter {cid!r}: invalid {derive_file.name}: {exc}")
                derive_data = {}
            title = str((derive_data or {}).get("display_title", "")).strip()
            if not title:
                errors.append(f"chapter {cid!r}: display_title missing in {derive_file.name}")

        body_file = chapter_body_path(revision_dir, cid)
        if not body_file.is_file():
            errors.append(f"chapter {cid!r}: missing {body_file.name}")
        elif not body_file.read_text(encoding="utf-8").strip():
            errors.append(f"chapter {cid!r}: empty body file {body_file.name}")

        if not chapter_anchor_present(raw_doc, cid):
            errors.append(f"chapter {cid!r}: missing chapter anchor in compose document")
        else:
            segment_lines = chapter_body_by_id(raw_doc, cid).splitlines()
            first_line = segment_lines[0].strip() if segment_lines else ""
            if first_line.startswith("## ") and not first_line.startswith("### "):
                segment_lines = segment_lines[1:]
            if not "\n".join(segment_lines).strip():
                errors.append(f"chapter {cid!r}: compose document empty chapter body")

    if not errors:
        return None
    return "; ".join(errors)


def validate_init_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None when all checks pass."""
    if not revision_dir.is_dir():
        return f"revision dir not found: {revision_dir}"

    if not compose_doc.is_file():
        return f"compose document not found: {compose_doc}"

    return validate_display_layer_artifacts(
        revision_dir, compose_doc, project_root, profile_id,
    )


def cmd_validate(args: argparse.Namespace) -> int:
    error = validate_init_artifacts(
        args.revision_dir.resolve(),
        args.compose_doc.resolve(),
        args.project_root.resolve(),
        args.profile.strip(),
    )
    if error:
        print(f"错误：Init 校验失败：{error}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Validate Init derive artifacts")
    validate_parser.add_argument("--revision-dir", type=Path, required=True)
    validate_parser.add_argument("--compose-doc", type=Path, required=True)
    validate_parser.add_argument("--profile", type=str, required=True)
    validate_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
