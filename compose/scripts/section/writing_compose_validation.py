#!/usr/bin/env python3
"""Validate Writing display-layer artifacts and compose document seed.

Subcommands:
    validate    Check revision-dir facts/chapters/derive/body and compose doc

CLI details: ``python3 writing_compose_validation.py --help``
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

from chapter_artifact_paths import chapter_body_path  # noqa: E402
from chapter_doc_schema import chapter_anchor_present, chapter_body_by_id  # noqa: E402
from chapter_fc_gates import check_chapter_write_artifacts  # noqa: E402
from discussion_pointer_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402


def section_order_for_profile(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    sections = data.get("sections") or {}
    if isinstance(sections, dict) and sections:
        return [str(key).upper() for key in sections]
    return [str(key).upper() for key in data.get("section_order") or []]

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
) -> list[str]:
    """Chapter body write artifacts + compose-doc assembly completeness."""
    errors: list[str] = []
    raw_doc = compose_doc.read_text(encoding="utf-8")
    for chapter in chapters_view:
        if chapter.get("op") == "drop":
            continue
        cid = str(chapter.get("id", "")).strip()

        for err in check_chapter_write_artifacts(revision_dir, cid):
            # Preserve prior phrasing for empty-body file errors in Step 5.
            if err.startswith("empty body:"):
                body_name = err.split(":", 1)[1].strip()
                errors.append(f"5.A: chapter {cid!r}: empty body file {body_name}")
            elif err.startswith("missing body:"):
                body_name = err.split(":", 1)[1].strip()
                errors.append(f"5.A: chapter {cid!r}: missing {body_name}")
            else:
                errors.append(f"5.A: chapter {cid!r}: {err}")

        if not chapter_anchor_present(raw_doc, cid):
            errors.append(
                f"5.A: chapter {cid!r}: missing chapter anchor in compose document",
            )
        else:
            segment_lines = chapter_body_by_id(raw_doc, cid).splitlines()
            first_line = segment_lines[0].strip() if segment_lines else ""
            # Strip optional visible titles inside the chapter segment (legacy ## /
            # debug #### lens heading). Leaf/group titles sit outside anchors.
            if first_line.startswith("#### "):
                segment_lines = segment_lines[1:]
            elif first_line.startswith("## ") and not first_line.startswith("### "):
                segment_lines = segment_lines[1:]
            if not "\n".join(segment_lines).strip():
                errors.append(
                    f"5.A: chapter {cid!r}: compose document empty chapter body",
                )
    return errors


def _validate_narrative_arc_display_layer(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
    facts: list[dict[str, Any]],
) -> str | None:
    """archive-5.0 path: ``_narrative-arc.json`` is chapter SoT."""
    from narrative_arc_schema import (
        load_narrative_arc,
        narrative_arc_path,
        validate_narrative_arc,
    )

    path = narrative_arc_path(revision_dir)
    allowed = set(section_order_for_profile(project_root, profile_id))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"3.2: invalid _narrative-arc.json: {exc}"
    errors = validate_narrative_arc(data, facts=facts, allowed_lenses=allowed or None)
    if errors:
        return "3.2: invalid narrative arc: " + "; ".join(errors)
    if str(data.get("status", "")).strip() != "write_ready":
        return "3.2: narrative arc status must be write_ready"
    try:
        load_narrative_arc(path, facts=facts, allowed_lenses=allowed or None)
    except ValueError as exc:
        return f"3.2: invalid narrative arc: {exc}"

    chapters_view: list[dict[str, Any]] = []
    for leaf in data.get("leaves") or []:
        leaf_id = str(leaf.get("id", "")).strip()
        for chapter in leaf.get("chapters") or []:
            lens = str(chapter.get("lens", "")).strip().upper()
            cid = f"{leaf_id}-{lens}"
            chapters_view.append(
                {
                    "id": cid,
                    "facts": [
                        {"fid": str(fid).strip()}
                        for fid in (chapter.get("fact_ids") or [])
                    ],
                }
            )

    errors_out: list[str] = []
    errors_out.extend(
        _check_chapter_artifacts_and_assembly(
            revision_dir,
            compose_doc,
            chapters_view,
        )
    )
    errors_out.extend(check_fact_anchor_coverage(revision_dir, facts, chapters_view))
    if not errors_out:
        return None
    return "; ".join(errors_out)


def validate_display_layer_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None — narrative-arc Writing validation.

    SoT: ``_facts.json`` + ``_narrative-arc.json`` + chapter write-state.
    Retired (error if present): ``_chapters.json``, ``_lens-themes.json``,
    ``_chapter-framework.json``, ``_chapter-placement.json``.
    """
    retired = (
        ("_chapters.json", "_narrative-arc.json"),
        ("_lens-themes.json", "_narrative-arc.json"),
        ("_chapter-framework.json", "_narrative-arc.json"),
        ("_chapter-placement.json", "_narrative-arc.json"),
    )
    for name, sot in retired:
        if (revision_dir / name).is_file():
            return (
                f"retired: {name} present — delete it; chapter plan SoT is {sot}"
            )

    try:
        facts = load_facts(facts_path(revision_dir))
    except ValueError as exc:
        return f"invalid or missing _facts.json: {exc}"

    arc_path = revision_dir / "_narrative-arc.json"
    if not arc_path.is_file():
        return "3.2: missing _narrative-arc.json"

    from chapter_write_state_schema import require_complete  # local import

    ws_err = require_complete(revision_dir)
    if ws_err:
        return f"4.W: {ws_err}"
    return _validate_narrative_arc_display_layer(
        revision_dir, compose_doc, project_root, profile_id, facts,
    )


def validate_writing_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None when all checks pass."""
    revision_dir = active_slice_dir(Path(revision_dir).resolve())
    if not revision_dir.is_dir():
        return f"revision dir not found: {revision_dir}"

    if not compose_doc.is_file():
        return f"compose document not found: {compose_doc}"

    return validate_display_layer_artifacts(
        revision_dir, compose_doc, project_root, profile_id,
    )


def cmd_validate(args: argparse.Namespace) -> int:
    error = validate_writing_artifacts(
        args.revision_dir.resolve(),
        args.compose_doc.resolve(),
        args.project_root.resolve(),
        args.profile.strip(),
    )
    if error:
        print(f"错误：Writing 校验失败：{error}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Validate Writing display-layer artifacts")
    validate_parser.add_argument("--revision-dir", type=Path, required=True)
    validate_parser.add_argument("--compose-doc", type=Path, required=True)
    validate_parser.add_argument("--profile", type=str, required=True)
    validate_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
