#!/usr/bin/env python3
"""Open-point loop control: opens, state, batches, receipts, and close checks.

The store is the unique writer. This CLI takes compose_state_lock on the
working slice, then calls the store.

Subcommands print JSON to stdout. Exit 0 on success, exit 1 on
validation / stale / invariant errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_INDUCTIVE = _HERE.parent
_COMPOSE_SCRIPTS = _INDUCTIVE.parent
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_KERNEL = _COMPOSE_SCRIPTS / "_kernel"
_SCOPE = _COMPOSE_SCRIPTS / "schema" / "section" / "scope"
_TEMPLATES = _COMPOSE_SCRIPTS / "templates"
_SCHEMA_DIRS = (
    _INDUCTIVE / "schema" / "gate",
    _INDUCTIVE / "schema" / "topic",
    _INDUCTIVE / "schema" / "open-point",
    _INDUCTIVE / "schema" / "recompose",
)
for _path in (_HERE, *_SCHEMA_DIRS, _SESSION, _KERNEL, _SCOPE, _TEMPLATES):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import compose_state_lock  # noqa: E402
from domain_instance_schema import load_and_validate_domain_instance  # noqa: E402
from inductive_gate_state_schema import load_gate_state  # noqa: E402
from execution_state_schema import working_execution_dir  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from open_point_store import (  # noqa: E402
    RepairRequiredError,
    StaleError,
    active_batch_of,
    add_opens,
    attach_code_refs,
    check_close,
    defer_open,
    ensure_frontier,
    FACTS_BASENAME,
    frontier_digest,
    frontier_skip,
    frontier_unskip,
    detect_lens_context,
    detect_opens_snapshot,
    load_bundle,
    pending_lenses,
    require_detect_ruler,
    reject_open,
    set_frontier,
    skip_open,
    update_open,
)


def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


def _parse_json(raw: str, label: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"invalid {label}: {exc}")
    raise AssertionError("unreachable")


def _active_open(bundle: dict[str, Any]) -> dict[str, Any] | None:
    open_id = bundle["state"].get("active_open_id")
    if not open_id:
        return None
    return next((item for item in bundle["opens"] if item["id"] == open_id), None)


def _gate_state_path(slice_dir: Path, args: argparse.Namespace) -> Path:
    seen: set[Path] = set()
    for base in (Path(args.out_dir), slice_dir, slice_dir.parent):
        path = Path(base).resolve() / "inductive-gate-state.json"
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    raise ValueError("detect-context failed: gate state not found; run init-session first")


def _detect_guide(slice_dir: Path, args: argparse.Namespace) -> dict[str, str]:
    root = str(getattr(args, "project_root", "") or "").strip()
    if not root:
        raise ValueError("detect-context failed: --project-root is required to load guide")
    state = load_gate_state(_gate_state_path(slice_dir, args))
    stage = str(state.get("stage") or "").strip()
    if not stage:
        raise ValueError(
            "detect-context failed: gate-state.stage is empty; "
            "cannot resolve domain instance"
        )
    cycle_type = detect_cycle_type(str(state.get("cycle_id") or ""))
    try:
        domain = load_and_validate_domain_instance(
            cycle_type,
            project_root=Path(root).resolve(),
            profile_id=stage,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        raise ValueError(f"guide unresolved: {exc}") from exc
    return {
        "cognitive_frame": str(domain["cognitive_frame"]),
        "intent_anchor": str(domain["intent_anchor"]),
    }


def cmd_resolve_context(slice_dir: Path, _args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _ok(
        {
            "opens": bundle["opens"],
            "state": bundle["state"],
            "active_batch": active_batch_of(bundle),
            "close": {
                "cleared": check_close(
                    slice_dir,
                    mode="cleared",
                    project_root=getattr(_args, "project_root", "") or None,
                ),
                "hard-skip": check_close(
                    slice_dir,
                    mode="hard-skip",
                    project_root=getattr(_args, "project_root", "") or None,
                ),
            },
        }
    )


def cmd_ensure_frontier(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    if bundle["state"]["phase"] != "idle":
        raise ValueError("ensure-frontier requires idle (currently processing)")
    project_root = Path(args.project_root).resolve() if args.project_root else None
    frontiers = ensure_frontier(slice_dir, project_root)
    _ok({"frontiers": frontiers, "frontier_digest": frontier_digest(slice_dir)})


def cmd_detect_context(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    if bundle["state"]["phase"] != "idle":
        raise ValueError("detect-context requires idle (currently processing)")
    project_root = Path(args.project_root).resolve() if args.project_root else None
    require_detect_ruler(slice_dir, project_root)
    _ok(
        {
            "opens_snapshot": detect_opens_snapshot(bundle["opens"]),
            "pending_lenses": pending_lenses(slice_dir, project_root),
            "guide": _detect_guide(slice_dir, args),
        }
    )


def cmd_detect_lens_context(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    if bundle["state"]["phase"] != "idle":
        raise ValueError("detect-lens-context requires idle (currently processing)")
    project_root = Path(args.project_root).resolve() if args.project_root else None
    require_detect_ruler(slice_dir, project_root)
    _ok(detect_lens_context(slice_dir, args.lens, project_root))


def cmd_process_context(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    current_open = _active_open(bundle)
    if current_open is None:
        raise ValueError("no active open")
    payload: dict[str, Any] = {
        "open": current_open,
        "facts_path": str((slice_dir / FACTS_BASENAME).resolve()),
    }
    if args.project_root:
        payload["project_evidence_scope"] = {
            "project_root": str(Path(args.project_root).resolve())
        }
    _ok(payload)


def cmd_add_opens(slice_dir: Path, args: argparse.Namespace) -> None:
    opens = _parse_json(args.opens_json, "--opens-json")
    if not isinstance(opens, list):
        raise ValueError("--opens-json must be a JSON array")
    detect = None
    if args.detect_json:
        detect = _parse_json(args.detect_json, "--detect-json")
        if not isinstance(detect, dict):
            raise ValueError("--detect-json must be a JSON object")
    result = add_opens(
        slice_dir,
        opens=opens,
        detect=detect,
        project_root=args.project_root or None,
    )
    _ok(result)


def cmd_update_open(slice_dir: Path, args: argparse.Namespace) -> None:
    patch = _parse_json(args.patch_json, "--patch-json")
    if not isinstance(patch, dict):
        raise ValueError("--patch-json must be a JSON object")
    _ok(update_open(slice_dir, args.open_id, patch))


def cmd_defer_open(slice_dir: Path, args: argparse.Namespace) -> None:
    _ok(defer_open(slice_dir, args.open_id, args.note))


def cmd_reject_open(slice_dir: Path, args: argparse.Namespace) -> None:
    _ok(reject_open(slice_dir, args.open_id, args.reason))


def cmd_skip_open(slice_dir: Path, args: argparse.Namespace) -> None:
    _ok(skip_open(slice_dir, args.open_id))


def cmd_attach_code_refs(slice_dir: Path, args: argparse.Namespace) -> None:
    refs = _parse_json(args.refs_json, "--refs-json")
    if not isinstance(refs, list):
        raise ValueError("--refs-json must be a JSON array")
    _ok(attach_code_refs(slice_dir, args.open_id, refs))


def cmd_check_close(slice_dir: Path, args: argparse.Namespace) -> None:
    result = check_close(
        slice_dir,
        mode=args.mode,
        project_root=args.project_root or None,
    )
    if not result["ok"]:
        raise ValueError("; ".join(result["reasons"]) or "close check failed")
    _ok({**result, "state": load_bundle(slice_dir)["state"]})


def cmd_set_frontier(slice_dir: Path, args: argparse.Namespace) -> None:
    project_root = Path(args.project_root).resolve() if args.project_root else None
    _ok(
        {
            "frontier": set_frontier(
                slice_dir, args.lens, args.kw, project_root=project_root
            )
        }
    )


def cmd_frontier_skip(slice_dir: Path, args: argparse.Namespace) -> None:
    project_root = Path(args.project_root).resolve() if args.project_root else None
    _ok(
        {
            "frontier": frontier_skip(
                slice_dir, args.lens, args.note, project_root=project_root
            )
        }
    )


def cmd_frontier_unskip(slice_dir: Path, args: argparse.Namespace) -> None:
    project_root = Path(args.project_root).resolve() if args.project_root else None
    _ok(
        {
            "frontier": frontier_unskip(
                slice_dir, args.lens, project_root=project_root
            )
        }
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", required=True, metavar="PATH")
    parser.add_argument(
        "--project-root",
        default="",
        help="Session root for skill templates, frontier, and process-context scope",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("resolve-context", help="Opens + state + active batch + close summary")
    sub.add_parser(
        "ensure-frontier",
        help="Initialize or merge lens-frontier.json from section-registry",
    )
    sub.add_parser(
        "detect-context",
        help=(
            "Read-only opens_snapshot, pending_lenses, and guide. "
            "pending_lenses = registry-ordered lens keys due for detection "
            "this pass; lenses whose clean fingerprint still holds are "
            "carried by control and omitted. guide is Domain "
            "cognitive_frame + intent_anchor; fails if --project-root, "
            "gate-state, stage, or Domain is missing. Does not emit facts, "
            "KW, or lens registry."
        ),
    )
    lens_ctx = sub.add_parser(
        "detect-lens-context",
        help=(
            "Read-only, one lens: kw_criteria with only rows "
            "KW>=max(ledger frontier,1) (KW0 never), one registry row, "
            "and id/text of facts whose lens is --lens. "
            "Does not emit frontier_kw. Unknown lens errors."
        ),
    )
    lens_ctx.add_argument("--lens", required=True)
    sub.add_parser(
        "process-context",
        help="Active open + facts_path; project scope when --project-root",
    )

    add = sub.add_parser(
        "add-opens",
        help=(
            "Register 0..N opens. Detect must pass --detect-json "
            '{"verdicts": [{lens, gap_kw, candidates[]}, ...]} covering '
            "exactly the detect-context pending_lenses; gap_kw is null "
            "exactly when candidates is empty. Empty --opens-json is legal "
            "only with detect metadata. Measurements and the receipt derive "
            "from verdicts; carried lenses get gap_kw null. AI Detect means "
            "must be probe. Non-null gap_kw writes "
            "that lens frontier_kw and drops clean; null records clean."
        ),
    )
    add.add_argument("--opens-json", required=True)
    add.add_argument("--detect-json", default="")

    update = sub.add_parser("update-open", help="Patch question/basis/blocking")
    update.add_argument("--open-id", required=True)
    update.add_argument("--patch-json", required=True)

    defer = sub.add_parser("defer-open", help="Defer the active open")
    defer.add_argument("--open-id", required=True)
    defer.add_argument("--note", required=True)

    reject = sub.add_parser("reject-open", help="Reject the active open")
    reject.add_argument("--open-id", required=True)
    reject.add_argument("--reason", required=True)

    skip = sub.add_parser("skip-open", help="Move the active open to the batch tail")
    skip.add_argument("--open-id", required=True)

    attach = sub.add_parser("attach-code-refs", help="Attach code refs to an open")
    attach.add_argument("--open-id", required=True)
    attach.add_argument("--refs-json", required=True)

    close = sub.add_parser(
        "check-close",
        help="Predicate only; does not close G3 or abandon a batch",
    )
    close.add_argument("--mode", required=True, choices=("cleared", "hard-skip"))
    close.add_argument(
        "--confirm",
        action="store_true",
        help="Ignored; G3 close is $INDUCTIVE_GATE_CTL gate-close --confirm",
    )

    _SET_FRONTIER = (
        "Human override of one lens resume start X. Not for Detect gaps "
        "(those write via add-opens verdicts). Detect again before "
        "cleared."
    )
    frontier = sub.add_parser(
        "set-frontier",
        help=_SET_FRONTIER,
        description=_SET_FRONTIER,
    )
    frontier.add_argument("--lens", required=True)
    frontier.add_argument("--kw", required=True, type=int)

    _FRONTIER_SKIP = (
        "Mark a required lens as not blocking cleared. Not for Detect "
        "gaps. Detect again before cleared."
    )
    skip_f = sub.add_parser(
        "frontier-skip",
        help=_FRONTIER_SKIP,
        description=_FRONTIER_SKIP,
    )
    skip_f.add_argument("--lens", required=True)
    skip_f.add_argument("--note", required=True)

    unskip = sub.add_parser("frontier-unskip", help="Restore a skipped required lens")
    unskip.add_argument("--lens", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    slice_dir = working_execution_dir(Path(args.out_dir))
    dispatch = {
        "resolve-context": cmd_resolve_context,
        "ensure-frontier": cmd_ensure_frontier,
        "detect-context": cmd_detect_context,
        "detect-lens-context": cmd_detect_lens_context,
        "process-context": cmd_process_context,
        "add-opens": cmd_add_opens,
        "update-open": cmd_update_open,
        "defer-open": cmd_defer_open,
        "reject-open": cmd_reject_open,
        "skip-open": cmd_skip_open,
        "attach-code-refs": cmd_attach_code_refs,
        "check-close": cmd_check_close,
        "set-frontier": cmd_set_frontier,
        "frontier-skip": cmd_frontier_skip,
        "frontier-unskip": cmd_frontier_unskip,
    }
    with compose_state_lock(slice_dir):
        try:
            dispatch[args.subcommand](slice_dir, args)
        except StaleError:
            _fail("stale")
        except RepairRequiredError:
            _fail("repair_required")
        except ValueError as exc:
            _fail(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
