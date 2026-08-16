#!/usr/bin/env python3
"""Open-point loop control: opens, state, batches, receipts, and close checks.

The store is the unique writer. This CLI takes compose_state_lock on the
working slice, then calls the store.

Subcommands print JSON to stdout. Exit 0 on success, exit 1 on
validation / stale / invariant errors.

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
_SCHEMA = _HERE / "schema"
_COMPOSE_SCRIPTS = _HERE.parent
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_SECTION = _COMPOSE_SCRIPTS / "section"
for _path in (_HERE, _SCHEMA, _SESSION, _SECTION):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import canonical_digest, compose_state_lock  # noqa: E402
from l_ledger_schema import working_slice_dir  # noqa: E402
from open_point_store import (  # noqa: E402
    RepairRequired,
    StaleError,
    active_batch_of,
    add_opens,
    attach_code_refs,
    check_close,
    defer_open,
    facts_digest,
    facts_snapshot,
    lens_digest,
    lens_snapshot,
    load_bundle,
    reject_open,
    settle_open,
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


def _parse_id_list(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("["):
        data = _parse_json(text, "--resolved-by")
        if not isinstance(data, list):
            _fail("--resolved-by JSON must be a list")
        return [str(item).strip() for item in data if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def _active_open(bundle: dict[str, Any]) -> dict[str, Any] | None:
    open_id = bundle["state"].get("active_open_id")
    if not open_id:
        return None
    return next((item for item in bundle["opens"] if item["id"] == open_id), None)


def _require_fresh(slice_dir: Path, args: argparse.Namespace, bundle: dict[str, Any]) -> None:
    current_open = _active_open(bundle)
    current_batch = active_batch_of(bundle)
    if (
        args.facts_digest != facts_digest(slice_dir)
        or args.open_digest != (canonical_digest(current_open) if current_open else "")
        or args.batch_digest != (canonical_digest(current_batch) if current_batch else "")
    ):
        raise StaleError()


def cmd_resolve_context(slice_dir: Path, _args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _ok(
        {
            "opens": bundle["opens"],
            "state": bundle["state"],
            "active_batch": active_batch_of(bundle),
            "close": {
                "cleared": check_close(slice_dir, mode="cleared"),
                "hard-skip": check_close(slice_dir, mode="hard-skip"),
            },
        }
    )


def cmd_detect_context(slice_dir: Path, _args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    if bundle["state"]["phase"] != "idle":
        raise ValueError("detect-context requires idle (currently processing)")
    facts = facts_snapshot(slice_dir)
    lenses = lens_snapshot(slice_dir)
    _ok(
        {
            "facts": facts,
            "facts_digest": canonical_digest(facts),
            "lenses": lenses,
            "lens_digest": canonical_digest(lenses),
            "opens": bundle["opens"],
            "opens_digest": canonical_digest(bundle["opens"]),
        }
    )


def cmd_process_context(slice_dir: Path, _args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    current_open = _active_open(bundle)
    if current_open is None:
        raise ValueError("no active open")
    current_batch = active_batch_of(bundle)
    facts = facts_snapshot(slice_dir)
    _ok(
        {
            "open": current_open,
            "facts": facts,
            "facts_digest": canonical_digest(facts),
            "open_digest": canonical_digest(current_open),
            "batch_digest": canonical_digest(current_batch) if current_batch else "",
        }
    )


def cmd_add_opens(slice_dir: Path, args: argparse.Namespace) -> None:
    opens = _parse_json(args.opens_json, "--opens-json")
    if not isinstance(opens, list):
        raise ValueError("--opens-json must be a JSON array")
    detect = None
    if args.detect_json:
        detect = _parse_json(args.detect_json, "--detect-json")
        if not isinstance(detect, dict):
            raise ValueError("--detect-json must be a JSON object")
    result = add_opens(slice_dir, opens=opens, detect=detect)
    _ok(result)


def cmd_update_open(slice_dir: Path, args: argparse.Namespace) -> None:
    patch = _parse_json(args.patch_json, "--patch-json")
    if not isinstance(patch, dict):
        raise ValueError("--patch-json must be a JSON object")
    bundle = load_bundle(slice_dir)
    _require_fresh(slice_dir, args, bundle)
    _ok(update_open(slice_dir, args.open_id, patch))


def cmd_defer_open(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _require_fresh(slice_dir, args, bundle)
    _ok(defer_open(slice_dir, args.open_id, args.note))


def cmd_reject_open(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _require_fresh(slice_dir, args, bundle)
    _ok(reject_open(slice_dir, args.open_id, args.reason))


def cmd_skip_open(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _require_fresh(slice_dir, args, bundle)
    _ok(skip_open(slice_dir, args.open_id))


def cmd_settle_resolved(slice_dir: Path, args: argparse.Namespace) -> None:
    bundle = load_bundle(slice_dir)
    _require_fresh(slice_dir, args, bundle)
    _ok(settle_open(slice_dir, args.open_id, _parse_id_list(args.resolved_by)))


def cmd_attach_code_refs(slice_dir: Path, args: argparse.Namespace) -> None:
    refs = _parse_json(args.refs_json, "--refs-json")
    if not isinstance(refs, list):
        raise ValueError("--refs-json must be a JSON array")
    _ok(attach_code_refs(slice_dir, args.open_id, refs))


def cmd_check_close(slice_dir: Path, args: argparse.Namespace) -> None:
    result = check_close(slice_dir, mode=args.mode)
    if not result["ok"]:
        raise ValueError("; ".join(result["reasons"]) or "close check failed")
    _ok({**result, "state": load_bundle(slice_dir)["state"]})


def _add_freshness_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--facts-digest", required=True)
    parser.add_argument("--open-digest", required=True)
    parser.add_argument("--batch-digest", required=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", required=True, metavar="PATH")
    parser.add_argument("--project-root", default="", help="Accepted; unused this task")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("resolve-context", help="Opens + state + active batch + close summary")
    sub.add_parser("detect-context", help="Facts/lens/opens snapshots + digests")
    sub.add_parser("process-context", help="Active open + facts + freshness digests")

    add = sub.add_parser(
        "add-opens",
        help=(
            "Register 0..N opens. Detect must pass --detect-json "
            "(checked_lenses, facts/lens/opens digests or expected_*, "
            "raw_candidates). Empty --opens-json is legal only with detect "
            "metadata. zero_result is raw_candidates length == 0."
        ),
    )
    add.add_argument("--opens-json", required=True)
    add.add_argument("--detect-json", default="")

    update = sub.add_parser("update-open", help="Patch question/basis/blocking")
    update.add_argument("--open-id", required=True)
    update.add_argument("--patch-json", required=True)
    _add_freshness_flags(update)

    defer = sub.add_parser("defer-open", help="Defer the active open")
    defer.add_argument("--open-id", required=True)
    defer.add_argument("--note", required=True)
    _add_freshness_flags(defer)

    reject = sub.add_parser("reject-open", help="Reject the active open")
    reject.add_argument("--open-id", required=True)
    reject.add_argument("--reason", required=True)
    _add_freshness_flags(reject)

    skip = sub.add_parser("skip-open", help="Move the active open to the batch tail")
    skip.add_argument("--open-id", required=True)
    _add_freshness_flags(skip)

    settle = sub.add_parser("settle-resolved", help="Settle an already-resolved open")
    settle.add_argument("--open-id", required=True)
    settle.add_argument("--resolved-by", required=True)
    _add_freshness_flags(settle)

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    slice_dir = working_slice_dir(Path(args.out_dir))
    dispatch = {
        "resolve-context": cmd_resolve_context,
        "detect-context": cmd_detect_context,
        "process-context": cmd_process_context,
        "add-opens": cmd_add_opens,
        "update-open": cmd_update_open,
        "defer-open": cmd_defer_open,
        "reject-open": cmd_reject_open,
        "skip-open": cmd_skip_open,
        "settle-resolved": cmd_settle_resolved,
        "attach-code-refs": cmd_attach_code_refs,
        "check-close": cmd_check_close,
    }
    with compose_state_lock(slice_dir):
        try:
            dispatch[args.subcommand](slice_dir, args)
        except StaleError:
            _fail("stale")
        except RepairRequired:
            _fail("repair_required")
        except ValueError as exc:
            _fail(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
