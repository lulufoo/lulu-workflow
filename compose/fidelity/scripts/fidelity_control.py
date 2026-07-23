#!/usr/bin/env python3
"""CLI for compose-internal fidelity Eval gate (doc→facts after Atomize).

Subcommands:
    init              Create pending fidelity-evaluate-state.md
    mark-passed       Mark E1∩E2 gate passed (Derive allowed)
    mark-skipped      Skip gate (e.g. unit-import intake; not Atomize)
    require-for-derive
                      Exit 0 only if status is passed|skipped
    status            Print JSON status
    paths             Print bound paths for probes (scope doc + facts)

Design: docs/domain/archive/compose/archive-3.0/compose-doc-ssot-facts-fidelity-eval-design.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_FIDELITY_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE_SCRIPTS = _FIDELITY_SCRIPTS.parents[1] / "scripts"
_SECTION = _COMPOSE_SCRIPTS / "section"
for p in (_FIDELITY_SCRIPTS, _COMPOSE_SCRIPTS, _SECTION):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from facts_schema import facts_path  # noqa: E402
from fidelity_evaluate_state_schema import (  # noqa: E402
    empty_state,
    fidelity_evaluate_state_path,
    gate_allows_derive,
    load_state,
    save_state,
)
from resolved_refs_schema import (  # noqa: E402
    has_resolved_refs,
    resolved_scope_ref,
)


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def cmd_init(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    path = fidelity_evaluate_state_path(rev)
    intake = (args.intake or "atomize").strip()
    data = empty_state(intake=intake)
    save_state(path, data)
    return _ok({"ok": True, "command": "init", "path": path.as_posix(), "status": "pending"})


def cmd_mark_passed(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    path = fidelity_evaluate_state_path(rev)
    if path.is_file():
        data = load_state(path)
    else:
        data = empty_state(intake="atomize")
    round_n = int(str(data.get("round", "0") or "0"))
    data["status"] = "passed"
    data["round"] = str(max(round_n, 1))
    data["skip_reason"] = ""
    save_state(path, data)
    return _ok({"ok": True, "command": "mark-passed", "path": path.as_posix(), "status": "passed"})


def cmd_mark_skipped(args: argparse.Namespace) -> int:
    reason = (args.reason or "").strip()
    if not reason:
        return _fail("mark-skipped requires --reason")
    rev = args.revision_dir.resolve()
    path = fidelity_evaluate_state_path(rev)
    data = empty_state(intake="unit-import")
    data["status"] = "skipped"
    data["skip_reason"] = reason
    save_state(path, data)
    return _ok(
        {
            "ok": True,
            "command": "mark-skipped",
            "path": path.as_posix(),
            "status": "skipped",
            "skip_reason": reason,
        }
    )


def cmd_require_for_derive(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    path = fidelity_evaluate_state_path(rev)
    if not path.is_file():
        return _fail(
            "fidelity gate missing — run Atomize fidelity Eval "
            f"(expected {path.name})",
        )
    data = load_state(path)
    if not gate_allows_derive(data):
        return _fail(
            f"fidelity gate not open (status={data.get('status')!r}); "
            "Derive blocked until E1∩E2 passed or skipped",
        )
    return _ok(
        {
            "ok": True,
            "command": "require-for-derive",
            "status": data.get("status"),
            "path": path.as_posix(),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    path = fidelity_evaluate_state_path(rev)
    if not path.is_file():
        return _ok({"ok": True, "exists": False, "path": path.as_posix()})
    data = load_state(path)
    return _ok(
        {
            "ok": True,
            "exists": True,
            "path": path.as_posix(),
            "status": data.get("status"),
            "intake": data.get("intake"),
            "round": data.get("round"),
            "max_rounds": data.get("max_rounds"),
            "allows_derive": gate_allows_derive(data),
        }
    )


def cmd_paths(args: argparse.Namespace) -> int:
    rev = args.revision_dir.resolve()
    scope = ""
    if has_resolved_refs(rev):
        ref = resolved_scope_ref(rev)
        if ref is not None:
            scope = ref.path
    return _ok(
        {
            "ok": True,
            "scope_doc": scope,
            "facts_path": facts_path(rev).as_posix(),
            "fidelity_state": fidelity_evaluate_state_path(rev).as_posix(),
            "dimension_defs_dir": (
                _FIDELITY_SCRIPTS.parent / "dimension-defs"
            ).resolve().as_posix(),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--revision-dir", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create pending fidelity state")
    init_p.add_argument("--intake", default="atomize")
    init_p.set_defaults(func=cmd_init)

    sub.add_parser("mark-passed", help="Mark gate passed").set_defaults(
        func=cmd_mark_passed,
    )

    skip_p = sub.add_parser("mark-skipped", help="Skip gate (non-Atomize intake)")
    skip_p.add_argument("--reason", required=True)
    skip_p.set_defaults(func=cmd_mark_skipped)

    sub.add_parser(
        "require-for-derive",
        help="Hard-fail unless passed|skipped",
    ).set_defaults(func=cmd_require_for_derive)

    sub.add_parser("status", help="JSON status").set_defaults(func=cmd_status)
    sub.add_parser("paths", help="Bound paths for E1/E2 probes").set_defaults(
        func=cmd_paths,
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
