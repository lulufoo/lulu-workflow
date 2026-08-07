#!/usr/bin/env python3
"""Narrative-arc collab control (archive-14.0 semantic builder target).

Persist an agent-authored semantic collaboration arc candidate. **Caller must
pass ``--output-path``** (collab ≠ Formal) and explicitly confirm overwrite.
The candidate must map every current fact to exactly one collab leaf. Existing
output is backed up before write; the control returns a fact→node summary.

Subcommands: write · validate · show

Formal Init path remains ``narrative_arc_control.py`` + ``_narrative-arc.json``.

CLI: ``python3 narrative_arc_collab_control.py --help``

Process how: docs/domain/archive/compose/archive-11.0/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
for _p in (_SCRIPTS, _RUNNER_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import active_slice_dir  # noqa: E402
from compose_state_lock import canonical_digest  # noqa: E402
from facts_schema import facts_path, load_facts  # noqa: E402
from narrative_arc_collab_schema import (  # noqa: E402
    assert_not_formal_path,
    collab_fact_coverage_errors,
    fact_node_summary,
    load_narrative_arc_collab,
    orphan_fact_ids,
    save_narrative_arc_collab,
    validate_narrative_arc_collab,
)


def _slice(revision_dir: str) -> Path:
    return active_slice_dir(Path(revision_dir).resolve())


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _resolve_output(args: argparse.Namespace) -> Path:
    raw = str(args.output_path or "").strip()
    if not raw:
        raise ValueError("--output-path is required (caller-supplied; collab ≠ Formal)")
    path = Path(raw)
    if not path.is_absolute():
        path = _slice(args.revision_dir) / path
    assert_not_formal_path(path)
    return path.resolve()


def _load_candidate(file_path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read candidate: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid candidate JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("collab candidate root must be an object")
    return data


def _current_facts(slice_dir: Path) -> list[dict[str, Any]]:
    path = facts_path(slice_dir)
    if not path.is_file():
        raise ValueError(f"facts not found: {path}")
    return load_facts(path)


def cmd_write(args: argparse.Namespace) -> int:
    if not args.confirm:
        return _fail("write requires --confirm (human-chosen only)")
    try:
        out_path = _resolve_output(args)
        arc = _load_candidate(args.file)
    except ValueError as exc:
        return _fail(str(exc))
    if args.digest != canonical_digest(arc):
        return _fail("write digest does not match the reviewed candidate")
    try:
        slice_dir = _slice(args.revision_dir)
        facts = _current_facts(slice_dir)
    except ValueError as exc:
        return _fail(str(exc))
    errors = validate_narrative_arc_collab(arc)
    errors.extend(collab_fact_coverage_errors(arc, facts))
    if errors:
        return _fail("; ".join(errors))

    try:
        backup_path: str | None = None
        if out_path.is_file():
            backup = out_path.with_suffix(out_path.suffix + f".bak.{int(time.time())}")
            shutil.copy2(out_path, backup)
            backup_path = str(backup)
        saved = save_narrative_arc_collab(out_path, arc)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))

    summary = fact_node_summary(saved)
    orphans = orphan_fact_ids(saved, facts)
    return _ok(
        {
            "ok": True,
            "command": "write",
            "path": str(out_path),
            "backup": backup_path,
            "leaf_count": len(saved.get("leaves") or []),
            "fact_node_summary": summary,
            "orphan_fact_ids": orphans,
        }
    )


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        out_path = _resolve_output(args)
    except ValueError as exc:
        return _fail(str(exc))
    if not out_path.is_file():
        return _fail(f"collab arc not found: {out_path}")
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")
    errors = validate_narrative_arc_collab(data)
    if errors:
        return _fail("; ".join(errors))
    slice_dir = _slice(args.revision_dir)
    fpath = facts_path(slice_dir)
    facts = load_facts(fpath) if fpath.is_file() else []
    orphans = orphan_fact_ids(data, facts)
    return _ok(
        {
            "ok": True,
            "path": str(out_path),
            "orphan_fact_ids": orphans,
            "stale": bool(orphans),
        }
    )


def cmd_show(args: argparse.Namespace) -> int:
    try:
        out_path = _resolve_output(args)
        data = load_narrative_arc_collab(out_path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok({"ok": True, "path": str(out_path), "arc": data})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text, fn in (
        ("write", "Human-chosen semantic candidate write + backup", cmd_write),
        ("validate", "Validate collab arc at --output-path", cmd_validate),
        ("show", "Print normalized collab arc", cmd_show),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--revision-dir", required=True)
        p.add_argument(
            "--output-path",
            required=True,
            help="Caller-supplied path (relative to slice or absolute); not Formal",
        )
        if name == "write":
            p.add_argument(
                "--file",
                required=True,
                help="Agent-authored semantic collab candidate JSON",
            )
            p.add_argument(
                "--confirm",
                action="store_true",
                help="Required; human-chosen overwrite",
            )
            p.add_argument(
                "--digest",
                required=True,
                help="Digest emitted by validate-candidate for the reviewed file",
            )
        p.set_defaults(func=fn)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
