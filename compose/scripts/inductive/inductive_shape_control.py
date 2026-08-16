#!/usr/bin/env python3
"""Stateless shape perception over the current working slice.

Reads facts, lens registry, and opens. Writes nothing.

Default command (or ``perceive``) prints JSON:
    facts_count, facts_digest, lenses, lenses_with_facts,
    lenses_without_facts, open_count, perception

Design rationale:
docs/domain/archive/compose/archive-34.0/compose-g3-open-point-loop-refactor-design.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_COMPOSE_SCRIPTS = _HERE.parent
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_SECTION = _COMPOSE_SCRIPTS / "section"
for _path in (_HERE, _SESSION, _SECTION):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import canonical_digest  # noqa: E402
from l_ledger_schema import working_slice_dir  # noqa: E402
from open_point_store import facts_snapshot, lens_snapshot  # noqa: E402
from opens_schema import load_opens, opens_path  # noqa: E402


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def _lenses_from_registry(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if not isinstance(raw, dict):
        return []
    order = raw.get("section_order")
    if isinstance(order, list) and order:
        return [str(item).strip() for item in order if str(item).strip()]
    sections = raw.get("sections")
    if isinstance(sections, dict):
        return [str(key).strip() for key in sections if str(key).strip()]
    return []


def _fact_lenses(facts: Any) -> set[str]:
    tagged: set[str] = set()
    if not isinstance(facts, list):
        return tagged
    for item in facts:
        if not isinstance(item, dict):
            continue
        tags = item.get("lens_tags")
        if not isinstance(tags, list):
            continue
        for tag in tags:
            cleaned = str(tag).strip()
            if cleaned:
                tagged.add(cleaned)
    return tagged


def _perception(
    *,
    facts_count: int,
    lenses: list[str],
    lenses_with_facts: list[str],
    open_count: int,
) -> str:
    if facts_count == 0 and not lenses:
        return (
            f"No facts file and no lens registry; {open_count} opens. "
            "Shape is uncertain."
        )
    return (
        f"{facts_count} facts; {len(lenses_with_facts)}/{len(lenses)} lenses "
        f"have facts; {open_count} opens remain. Coverage and remaining gaps "
        "are uncertain."
    )


def cmd_perceive(slice_dir: Path) -> None:
    facts = facts_snapshot(slice_dir)
    if not isinstance(facts, list):
        facts = []
    lenses = _lenses_from_registry(lens_snapshot(slice_dir))
    tagged = _fact_lenses(facts)
    lenses_with_facts = [lens for lens in lenses if lens in tagged]
    lenses_without_facts = [lens for lens in lenses if lens not in tagged]
    opens = load_opens(opens_path(slice_dir))
    open_count = sum(1 for item in opens if item.get("status") == "open")
    _ok(
        {
            "facts_count": len(facts),
            "facts_digest": canonical_digest(facts),
            "lenses": lenses,
            "lenses_with_facts": lenses_with_facts,
            "lenses_without_facts": lenses_without_facts,
            "open_count": open_count,
            "perception": _perception(
                facts_count=len(facts),
                lenses=lenses,
                lenses_with_facts=lenses_with_facts,
                open_count=open_count,
            ),
        }
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", required=True, metavar="PATH")
    parser.add_argument("--project-root", default="", help="Accepted; unused")
    sub = parser.add_subparsers(dest="subcommand")
    sub.add_parser("perceive", help="Print a coarse current-slice perception")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand not in (None, "perceive"):
        _fail(f"unknown subcommand: {args.subcommand!r}")
    cmd_perceive(working_slice_dir(Path(args.out_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
