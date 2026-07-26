#!/usr/bin/env python3
"""Control for archive-3.0 dynamic chapter plan artifacts.

Subcommands:
    write-themes      Persist ``_lens-themes.json``
    write-framework   Persist ``_chapter-framework.json``
    write-placement   Persist ``_chapter-placement.json`` (placement SoT)
    propose-placement C1 mechanical placement draft (+ C2 needs_resolution)
    list-chapters     Print render-order chapter ids (framework ∩ placement with facts)
    validate          Validate themes + framework + placement

CLI: ``python3 chapter_plan_control.py --help``

Process how: docs/domain/archive/compose/archive-3.0/compose-init-dynamic-chapter-framework-design.md
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

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from lens_themes_schema import (  # noqa: E402
    lens_themes_path,
    load_lens_themes,
    save_lens_themes,
    themes_by_fl,
)
from chapter_framework_schema import (  # noqa: E402
    chapter_framework_path,
    fl_to_chapter_id,
    load_chapter_framework,
    save_chapter_framework,
    validate_chapter_framework,
)
from chapter_placement_schema import (  # noqa: E402
    chapter_placement_path,
    load_chapter_placement,
    save_chapter_placement,
    validate_chapter_placement,
)
from placement_propose import propose_placement, themes_coverage_errors  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402


def _section_registry(project_root: Path, profile_id: str) -> dict[str, Any]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    return json.loads(raw)


def _section_order(project_root: Path, profile_id: str) -> list[str]:
    data = _section_registry(project_root, profile_id)
    sections = data.get("sections") or {}
    if isinstance(sections, dict) and sections:
        return [str(key).upper() for key in sections]
    return [str(key).upper() for key in data.get("section_order") or []]


def _required_lenses(project_root: Path, profile_id: str) -> list[str]:
    data = _section_registry(project_root, profile_id)
    sections = data.get("sections") or {}
    required: list[str] = []
    for lens in _section_order(project_root, profile_id):
        sec = sections.get(lens) or {}
        presence = str(sec.get("presence") or "required").strip().lower()
        if presence != "optional":
            required.append(lens)
    return required


def _load_facts_if_present(revision_dir: Path) -> list[dict[str, Any]]:
    path = facts_path(active_slice_dir(Path(revision_dir).resolve()))
    if not path.is_file():
        return []
    return load_facts(path)


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _read_json(path: Path | None, stdin_label: str) -> Any:
    try:
        if path:
            return json.loads(path.read_text(encoding="utf-8"))
        return json.loads(sys.stdin.read())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {stdin_label}: {exc}") from exc


def _reject_retired_chapters(revision_dir: Path) -> str | None:
    retired = revision_dir / "_chapters.json"
    if retired.is_file():
        return (
            "retired _chapters.json present — delete it; SoT is "
            "_lens-themes.json + _chapter-framework.json + _chapter-placement.json"
        )
    return None


def _render_chapter_ids(framework: dict[str, Any], placement: dict[str, Any]) -> list[str]:
    """Framework order ∩ placement chapters that have at least one fact.

    Empty placement chapters are skipped (5.A must not append them).
    """
    facts_by_cid = {
        c["id"]: list(c.get("facts") or [])
        for c in placement.get("chapters") or []
        if c.get("id")
    }
    return [
        c["id"]
        for c in framework.get("chapters") or []
        if c.get("id") in facts_by_cid and len(facts_by_cid[c["id"]]) > 0
    ]


def _rev(args: argparse.Namespace) -> Path:
    return active_slice_dir(args.revision_dir.resolve())


def cmd_write_themes(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    try:
        data = _read_json(args.themes_file, "themes JSON")
    except ValueError as exc:
        return _fail(str(exc))

    allowed = None
    required: list[str] = []
    if args.profile:
        try:
            root = args.project_root.resolve()
            profile = args.profile.strip()
            allowed = _section_order(root, profile)
            required = _required_lenses(root, profile)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"section-registry unavailable: {exc}")

    try:
        facts = _load_facts_if_present(revision_dir)
    except ValueError as exc:
        return _fail(f"invalid _facts.json: {exc}")

    coverage = themes_coverage_errors(
        data if isinstance(data, dict) else {},
        facts=facts,
        required_lenses=required,
        allowed_lenses=allowed,
    )
    if coverage:
        return _fail("; ".join(coverage))

    path = lens_themes_path(revision_dir)
    try:
        save_lens_themes(path, data, allowed_lenses=allowed)
    except ValueError as exc:
        return _fail(str(exc))
    loaded = load_lens_themes(path)
    return _ok(
        {
            "ok": True,
            "command": "write-themes",
            "path": str(path),
            "themes_total": len(loaded.get("lens_themes") or []),
        }
    )


def cmd_write_framework(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    try:
        data = _read_json(args.framework_file, "framework JSON")
    except ValueError as exc:
        return _fail(str(exc))

    try:
        themes = load_lens_themes(lens_themes_path(revision_dir))
    except ValueError as exc:
        return _fail(f"themes required before framework: {exc}")

    by_fl = themes_by_fl(themes)
    path = chapter_framework_path(revision_dir)
    try:
        save_chapter_framework(
            path,
            data,
            known_fl_ids=set(by_fl),
            themes_by_fl_id=by_fl,
        )
    except ValueError as exc:
        return _fail(str(exc))
    loaded = load_chapter_framework(path)
    return _ok(
        {
            "ok": True,
            "command": "write-framework",
            "path": str(path),
            "chapters_total": len(loaded.get("chapters") or []),
        }
    )


def cmd_write_placement(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    retired = _reject_retired_chapters(revision_dir)
    if retired:
        return _fail(retired)

    try:
        data = _read_json(args.placement_file, "placement JSON")
    except ValueError as exc:
        return _fail(str(exc))

    try:
        themes = load_lens_themes(lens_themes_path(revision_dir))
        framework = load_chapter_framework(chapter_framework_path(revision_dir))
    except ValueError as exc:
        return _fail(f"themes+framework required before placement: {exc}")

    known = set(themes_by_fl(themes))
    chapter_ids = {c["id"] for c in framework.get("chapters") or []}
    fl_map = fl_to_chapter_id(framework)

    path = chapter_placement_path(revision_dir)
    try:
        save_chapter_placement(
            path,
            data,
            known_fl_ids=known,
            chapter_ids=chapter_ids,
            fl_to_chapter=fl_map,
        )
    except ValueError as exc:
        return _fail(str(exc))

    placement = load_chapter_placement(path)
    return _ok(
        {
            "ok": True,
            "command": "write-placement",
            "path": str(path),
            "chapters_total": len(placement.get("chapters") or []),
            "facts_placed_total": sum(
                len(c.get("facts") or []) for c in placement.get("chapters") or []
            ),
            "chapter_ids": _render_chapter_ids(framework, placement),
        }
    )


def cmd_propose_placement(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    retired = _reject_retired_chapters(revision_dir)
    if retired:
        return _fail(retired)
    try:
        facts = load_facts(facts_path(revision_dir))
        themes = load_lens_themes(lens_themes_path(revision_dir))
        framework = load_chapter_framework(chapter_framework_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))

    proposal = propose_placement(facts, themes, framework)
    if args.write and not proposal["needs_resolution"] and not proposal["unmapped_facts"]:
        path = chapter_placement_path(revision_dir)
        try:
            save_chapter_placement(
                path,
                proposal["placement"],
                known_fl_ids=set(themes_by_fl(themes)),
                chapter_ids={c["id"] for c in framework.get("chapters") or []},
                fl_to_chapter=fl_to_chapter_id(framework),
            )
        except ValueError as exc:
            return _fail(str(exc))
        proposal["written"] = str(path)
    elif args.write:
        return _fail(
            "refuse --write: resolve needs_resolution / unmapped_facts first "
            f"(needs={proposal['needs_resolution_total']}, "
            f"unmapped={proposal['unmapped_total']})",
        )

    return _ok({"ok": True, "command": "propose-placement", **proposal})


def cmd_list_chapters(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    retired = _reject_retired_chapters(revision_dir)
    if retired:
        return _fail(retired)
    try:
        framework = load_chapter_framework(chapter_framework_path(revision_dir))
        placement = load_chapter_placement(chapter_placement_path(revision_dir))
    except ValueError as exc:
        return _fail(str(exc))
    ids = _render_chapter_ids(framework, placement)
    return _ok(
        {
            "ok": True,
            "command": "list-chapters",
            "chapter_ids": ids,
            "chapters_total": len(ids),
        }
    )


def cmd_validate(args: argparse.Namespace) -> int:
    revision_dir = _rev(args)
    retired = _reject_retired_chapters(revision_dir)
    if retired:
        return _fail(retired)
    try:
        themes = load_lens_themes(lens_themes_path(revision_dir))
        by_fl = themes_by_fl(themes)
        try:
            facts = _load_facts_if_present(revision_dir)
        except ValueError as exc:
            return _fail(f"invalid _facts.json: {exc}")
        required: list[str] = []
        allowed: list[str] | None = None
        if args.profile:
            try:
                root = args.project_root.resolve()
                profile = args.profile.strip()
                allowed = _section_order(root, profile)
                required = _required_lenses(root, profile)
            except Exception as exc:  # noqa: BLE001
                return _fail(f"section-registry unavailable: {exc}")
        coverage = themes_coverage_errors(
            themes,
            facts=facts,
            required_lenses=required,
            allowed_lenses=allowed,
        )
        if coverage:
            return _fail("; ".join(coverage))
        framework = load_chapter_framework(chapter_framework_path(revision_dir))
        fw_errors = validate_chapter_framework(
            framework,
            known_fl_ids=set(by_fl),
            themes_by_fl_id=by_fl,
        )
        if fw_errors:
            return _fail("; ".join(fw_errors))
        placement = load_chapter_placement(chapter_placement_path(revision_dir))
        pl_errors = validate_chapter_placement(
            placement,
            known_fl_ids=set(by_fl),
            chapter_ids={c["id"] for c in framework.get("chapters") or []},
            fl_to_chapter=fl_to_chapter_id(framework),
        )
        if pl_errors:
            return _fail("; ".join(pl_errors))
    except ValueError as exc:
        return _fail(str(exc))

    return _ok(
        {
            "ok": True,
            "command": "validate",
            "themes_total": len(themes.get("lens_themes") or []),
            "framework_chapters": len(framework.get("chapters") or []),
            "placement_chapters": len(placement.get("chapters") or []),
            "chapter_ids": _render_chapter_ids(framework, placement),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    wt = sub.add_parser("write-themes", help="Write _lens-themes.json")
    wt.add_argument("--revision-dir", type=Path, required=True)
    wt.add_argument("--themes-file", type=Path)
    wt.add_argument("--profile", type=str, default="")
    wt.add_argument("--project-root", type=Path, default=Path.cwd())
    wt.set_defaults(func=cmd_write_themes)

    wf = sub.add_parser("write-framework", help="Write _chapter-framework.json")
    wf.add_argument("--revision-dir", type=Path, required=True)
    wf.add_argument("--framework-file", type=Path)
    wf.add_argument("--project-root", type=Path, default=Path.cwd())
    wf.set_defaults(func=cmd_write_framework)

    wp = sub.add_parser(
        "write-placement",
        help="Write _chapter-placement.json (placement SoT)",
    )
    wp.add_argument("--revision-dir", type=Path, required=True)
    wp.add_argument("--placement-file", type=Path)
    wp.add_argument("--profile", type=str, default="")
    wp.add_argument("--project-root", type=Path, default=Path.cwd())
    wp.set_defaults(func=cmd_write_placement)

    pp = sub.add_parser(
        "propose-placement",
        help="C1 mechanical placement draft; lists C2 needs_resolution",
    )
    pp.add_argument("--revision-dir", type=Path, required=True)
    pp.add_argument(
        "--write",
        action="store_true",
        help="Persist placement only when needs_resolution and unmapped are empty",
    )
    pp.set_defaults(func=cmd_propose_placement)

    lc = sub.add_parser(
        "list-chapters",
        help="List chapter ids in render order (framework ∩ placement with facts)",
    )
    lc.add_argument("--revision-dir", type=Path, required=True)
    lc.set_defaults(func=cmd_list_chapters)

    val = sub.add_parser("validate", help="Validate themes/framework/placement")
    val.add_argument("--revision-dir", type=Path, required=True)
    val.add_argument("--profile", type=str, default="")
    val.add_argument("--project-root", type=Path, default=Path.cwd())
    val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
