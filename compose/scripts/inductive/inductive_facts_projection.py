#!/usr/bin/env python3
"""K2 mechanical projection: inductive ``decisions[]`` → unified ``_facts.json``.

Subcommands:
    project   Traverse section_order × decisions[] → write ``facts_path(revision)``

Design SSOT: docs/biz/compose-fact-first-theory/compose-fact-first-k2-inductive-design.md
§2–§5. Scripts never invent semantics — only renumber / tag / source-pack / save.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from facts_schema import facts_path, load_facts, save_facts  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from inductive_section_schema import validate_section  # noqa: E402

EMPTY_PROJECT_MSG = "no inductive decisions to project"


class EmptyProjectionError(ValueError):
    """Raised when every section's decisions[] is empty (facts_schema forbids [])."""


class OrphanSectionError(ValueError):
    """Raised when inductive section files outside section_order still have decisions."""


def build_source(decision: dict[str, Any]) -> list[str]:
    """Pack provenance into K1 ``source`` (default: always include decision id)."""
    parts: list[str] = []
    did = str(decision.get("id") or "").strip()
    if did:
        parts.append(did)
    intent_ref = decision.get("intent_ref")
    if isinstance(intent_ref, str) and intent_ref.strip():
        parts.append(intent_ref.strip())
    code_refs = decision.get("code_refs")
    if isinstance(code_refs, list):
        for item in code_refs:
            s = str(item).strip()
            if s:
                parts.append(s)
    return parts


def decision_to_fact(
    decision: dict[str, Any],
    *,
    section_key: str,
    fact_id: str,
) -> dict[str, Any]:
    """Map one decision to a minimal fact (1:1 lens_tags=[S]; rich fields stay sidecar)."""
    text = str(decision.get("text") or "").strip()
    if not text:
        raise ValueError(
            f"decision {decision.get('id')!r} in section {section_key}: empty text"
        )
    fact: dict[str, Any] = {
        "id": fact_id,
        "text": text,
        "lens_tags": [section_key.strip().upper()],
    }
    source = build_source(decision)
    if source:
        fact["source"] = source
    return fact


def orphan_sections_with_decisions(
    *,
    section_order: list[str],
    sections_by_key: dict[str, dict[str, Any]],
) -> list[str]:
    """Keys present on disk with non-empty decisions but absent from section_order."""
    order_set = {
        str(key).strip().upper() for key in section_order if str(key).strip()
    }
    orphans: list[str] = []
    for key, doc in sections_by_key.items():
        if key in order_set:
            continue
        for decision in doc.get("decisions") or []:
            if not isinstance(decision, dict):
                continue
            if str(decision.get("text") or "").strip():
                orphans.append(key)
                break
    return sorted(orphans)


def project_decisions_to_facts(
    *,
    section_order: list[str],
    sections_by_key: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Traverse ``section_order`` × each ``decisions[]``; renumber ``F-1..F-m``.

    Empty individual sections contribute nothing. All-empty → ``EmptyProjectionError``.
    Sections outside ``section_order`` with non-empty decisions → ``OrphanSectionError``
    (never silently drop).
    """
    orphans = orphan_sections_with_decisions(
        section_order=section_order,
        sections_by_key=sections_by_key,
    )
    if orphans:
        raise OrphanSectionError(
            "inductive sections outside section_order have decisions "
            f"(would be silently dropped): {orphans}"
        )

    facts: list[dict[str, Any]] = []
    n = 1
    for raw_key in section_order:
        key = str(raw_key).strip().upper()
        if not key:
            continue
        doc = sections_by_key.get(key)
        if doc is None:
            continue
        for decision in doc.get("decisions") or []:
            if not isinstance(decision, dict):
                continue
            facts.append(
                decision_to_fact(
                    decision,
                    section_key=key,
                    fact_id=f"F-{n}",
                )
            )
            n += 1
    if not facts:
        raise EmptyProjectionError(EMPTY_PROJECT_MSG)
    return facts


def load_sections_from_inductive_dir(inductive_dir: Path) -> dict[str, dict[str, Any]]:
    """Load ``{SECTION}.json`` files that live directly under inductive-scope."""
    root = Path(inductive_dir)
    if not root.is_dir():
        raise ValueError(f"inductive-dir not found or not a directory: {root}")
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        if path.name == "_index.json":
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path.name}: {exc}") from exc
        if not isinstance(doc, dict):
            raise ValueError(f"{path.name}: section root must be an object")
        errs = validate_section(doc)
        if errs:
            raise ValueError(f"invalid section {path.stem}: " + "; ".join(errs))
        key = str(doc.get("key") or path.stem).strip().upper()
        out[key] = doc
    return out


def _section_order(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    return [str(key).upper() for key in data.get("section_order") or []]


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_project(args: argparse.Namespace) -> int:
    revision_dir = args.revision_dir.resolve()
    inductive_dir = (
        args.inductive_dir.resolve()
        if args.inductive_dir is not None
        else (revision_dir / "inductive-scope")
    )
    try:
        sections = load_sections_from_inductive_dir(inductive_dir)
        order = _section_order(args.project_root.resolve(), args.profile.strip())
        if not order:
            return _fail("section-registry section_order is empty")
        facts = project_decisions_to_facts(
            section_order=order,
            sections_by_key=sections,
        )
        save_facts(facts_path(revision_dir), facts, allowed_lenses=order)
    except EmptyProjectionError as exc:
        return _fail(str(exc))
    except OrphanSectionError as exc:
        return _fail(str(exc))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 — surface framework fetch errors
        return _fail(f"section-registry unavailable: {exc}")

    loaded = load_facts(facts_path(revision_dir))
    return _ok(
        {
            "ok": True,
            "command": "project",
            "path": str(facts_path(revision_dir)),
            "facts_total": len(loaded),
            "sections_read": sorted(sections.keys()),
            "section_order": order,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    project_p = sub.add_parser(
        "project",
        help="Project inductive decisions[] into revision _facts.json",
    )
    project_p.add_argument("--revision-dir", type=Path, required=True)
    project_p.add_argument(
        "--inductive-dir",
        type=Path,
        default=None,
        help="Directory of {SECTION}.json (default: revision-dir/inductive-scope)",
    )
    project_p.add_argument("--profile", type=str, required=True)
    project_p.add_argument("--project-root", type=Path, default=Path.cwd())
    project_p.set_defaults(func=cmd_project)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
