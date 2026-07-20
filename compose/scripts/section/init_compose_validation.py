#!/usr/bin/env python3
"""Validate Initializing display-layer artifacts and compose document seed.

Subcommands:
    validate    Check revision-dir facts/chapters/derive/body and compose doc

CLI details: ``python3 init_compose_validation.py --help``
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

from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402
from chapter_doc_schema import chapter_anchor_present, chapter_body_by_id  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from outline_registry_schema import normalize_outline_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    dependency_graph_subset,
    normalize_section_registry,
)
from derive_shell import normalize_dependency_graph  # noqa: E402


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


def _fact_anchor_covered(anchor: dict[str, Any], body: str) -> bool:
    """True when an ``{kind, value}`` fact anchor survives into the body text.

    Substring match after normalization. ``code_ref`` values (``path::symbol``)
    are split on ``::`` and matched OR (any path/symbol segment present passes;
    §3.1). Trailing line-number parens are stripped.
    """
    value = str(anchor.get("value", "")).strip()
    if not value:
        return True
    if str(anchor.get("kind", "")).strip().lower() == "code_ref":
        cleaned = re.sub(r"\s*\(\d+\)\s*$", "", value).strip()
        segments = [seg.strip() for seg in cleaned.split("::") if seg.strip()]
        if segments:
            return any(seg in body for seg in segments)
        return cleaned in body
    return value in body


def check_fact_anchor_coverage(
    revision_dir: Path,
    facts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> list[str]:
    """L6: every discovered fact's anchors must survive into its chapter body.

    Strictness S1 (default): only facts with ``origin.type == discovered`` and
    non-empty ``anchors`` are enforced. Reads ``_body-{cid}.txt`` per non-drop
    chapter and requires each anchor value to appear (normalized substring).
    Returns error strings ``chapter_id / fid / anchor`` for any miss.
    """
    facts_by_id = {f.get("id"): f for f in facts}
    errors: list[str] = []
    for chapter in chapters:
        if chapter.get("op") == "drop":
            continue
        cid = str(chapter.get("id", "")).strip()
        body_file = chapter_body_path(revision_dir, cid)
        if not body_file.is_file():
            continue  # missing/empty body already reported by check #4
        body = body_file.read_text(encoding="utf-8")
        for fact_ref in chapter.get("facts", []):
            fid = str(fact_ref.get("fid", "")).strip()
            fact = facts_by_id.get(fid)
            if fact is None:
                continue
            origin_type = str((fact.get("origin") or {}).get("type", "")).strip().lower()
            if origin_type != "discovered":
                continue
            for anchor in fact.get("anchors") or []:
                if not _fact_anchor_covered(anchor, body):
                    errors.append(
                        f"L6: chapter {cid!r}: fact {fid} anchor "
                        f"{anchor.get('kind')}={anchor.get('value')!r} missing from body",
                    )
    return errors


def _check_chapter_artifacts_and_assembly(
    revision_dir: Path,
    compose_doc: Path,
    chapters_view: list[dict[str, Any]],
    *,
    framework_titles: dict[str, str] | None = None,
) -> list[str]:
    """Artifact existence + assembly completeness for rendered chapters."""
    errors: list[str] = []
    raw_doc = compose_doc.read_text(encoding="utf-8")
    for chapter in chapters_view:
        if chapter.get("op") == "drop":
            continue
        cid = str(chapter.get("id", "")).strip()

        derive_file = chapter_derive_path(revision_dir, cid)
        if not derive_file.is_file():
            errors.append(f"5.A: chapter {cid!r}: missing {derive_file.name}")
        else:
            try:
                derive_data = json.loads(derive_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"5.A: chapter {cid!r}: invalid {derive_file.name}: {exc}")
                derive_data = {}
            title = str((derive_data or {}).get("display_title", "")).strip()
            if not title:
                errors.append(
                    f"5.A: chapter {cid!r}: display_title missing in {derive_file.name}",
                )
            elif framework_titles is not None and cid in framework_titles:
                expected = framework_titles[cid]
                if title != expected:
                    errors.append(
                        f"5.A: chapter {cid!r}: display_title {title!r} != framework "
                        f"{expected!r}",
                    )

        body_file = chapter_body_path(revision_dir, cid)
        if not body_file.is_file():
            errors.append(f"5.A: chapter {cid!r}: missing {body_file.name}")
        elif not body_file.read_text(encoding="utf-8").strip():
            errors.append(f"5.A: chapter {cid!r}: empty body file {body_file.name}")

        if not chapter_anchor_present(raw_doc, cid):
            errors.append(
                f"5.A: chapter {cid!r}: missing chapter anchor in compose document",
            )
        else:
            segment_lines = chapter_body_by_id(raw_doc, cid).splitlines()
            first_line = segment_lines[0].strip() if segment_lines else ""
            if first_line.startswith("## ") and not first_line.startswith("### "):
                segment_lines = segment_lines[1:]
            if not "\n".join(segment_lines).strip():
                errors.append(
                    f"5.A: chapter {cid!r}: compose document empty chapter body",
                )
    return errors


def validate_display_layer_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None — fact-first Step 6 validation.

    Placement SoT only: ``_facts.json`` + ``_lens-themes.json`` +
    ``_chapter-framework.json`` + ``_chapter-placement.json``.
    ``_chapters.json`` is retired — its presence is an error.
    """
    errors: list[str] = []

    outline = outline_registry_for_profile(project_root, profile_id)
    if outline is None:
        return "failed to fetch/parse outline-registry for this profile"

    retired_chapters = revision_dir / "_chapters.json"
    if retired_chapters.is_file():
        return (
            "retired: _chapters.json present — delete it; chapter plan SoT is "
            "_lens-themes.json + _chapter-framework.json + _chapter-placement.json"
        )

    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return f"invalid or missing _facts.json: {exc}"

    framework_path = revision_dir / "_chapter-framework.json"
    placement_path = revision_dir / "_chapter-placement.json"
    themes_path = revision_dir / "_lens-themes.json"
    missing = [
        name
        for name, path in (
            ("_lens-themes.json", themes_path),
            ("_chapter-framework.json", framework_path),
            ("_chapter-placement.json", placement_path),
        )
        if not path.is_file()
    ]
    if missing:
        route_by_file = {
            "_lens-themes.json": "4.A",
            "_chapter-framework.json": "4.B",
            "_chapter-placement.json": "4.C",
        }
        route = route_by_file[missing[0]]
        return f"{route}: chapter plan incomplete: missing {', '.join(missing)}"

    presence_map = section_presence_map_for_profile(project_root, profile_id)
    section_order = section_order_for_profile(project_root, profile_id)
    dependency_graph = dependency_graph_for_profile(project_root, profile_id)

    try:
        from chapter_framework_schema import (
            fl_to_chapter_id,
            load_chapter_framework,
            validate_chapter_framework,
        )
        from chapter_placement_schema import (
            load_chapter_placement,
            validate_chapter_placement,
        )
        from lens_themes_schema import load_lens_themes, themes_by_fl
        from placement_plan_gates import (
            placement_chapters_as_l6_view,
            run_placement_plan_gates,
        )

        themes = load_lens_themes(themes_path)
        framework = load_chapter_framework(framework_path)
        known = set(themes_by_fl(themes))
        fw_errors = validate_chapter_framework(
            framework,
            known_fl_ids=known,
            themes_by_fl_id=themes_by_fl(themes),
        )
        if fw_errors:
            return "4.B: invalid chapter plan: " + "; ".join(fw_errors)
        placement = load_chapter_placement(placement_path)
        pl_errors = validate_chapter_placement(
            placement,
            known_fl_ids=known,
            chapter_ids={c["id"] for c in framework.get("chapters") or []},
            fl_to_chapter=fl_to_chapter_id(framework),
        )
        if pl_errors:
            return "4.C: invalid chapter plan: " + "; ".join(pl_errors)
    except ValueError as exc:
        msg = str(exc)
        if "_lens-themes" in msg or "lens_themes" in msg:
            return f"4.A: invalid chapter plan artifacts: {exc}"
        if "_chapter-framework" in msg or "chapter_framework" in msg:
            return f"4.B: invalid chapter plan artifacts: {exc}"
        if "_chapter-placement" in msg or "chapter_placement" in msg:
            return f"4.C: invalid chapter plan artifacts: {exc}"
        return f"4.B: invalid chapter plan artifacts: {exc}"

    gate_result = run_placement_plan_gates(
        facts,
        placement,
        themes,
        framework,
        presence_map=presence_map,
        section_order=section_order,
        dependency_graph=dependency_graph,
    )
    errors.extend(gate_result["errors"])
    chapters_view = placement_chapters_as_l6_view(placement)
    framework_titles = {
        c["id"]: c["display_title"] for c in framework.get("chapters") or []
    }
    errors.extend(
        _check_chapter_artifacts_and_assembly(
            revision_dir,
            compose_doc,
            chapters_view,
            framework_titles=framework_titles,
        )
    )
    errors.extend(check_fact_anchor_coverage(revision_dir, facts, chapters_view))

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
