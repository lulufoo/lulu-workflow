#!/usr/bin/env python3
"""Control for compose Facts (``_facts.json``).

Subcommands:
    write     Persist facts JSON (AI-produced) after schema validation
    filter    Print facts tagged with one lens as a JSON array (addressable)
    validate  Validate existing ``_facts.json``
    status    Print fact counts by lens tag (+ unlensed count)

    CLI details: ``python3 facts_control.py --help``

    ``write --target-l Lx`` buckets into ``revision/Lx/_facts.json`` (v1.1).
    If that L was ``production: done``, demotes it (FreeEdit when it is focus).

Design rationale (source repo, why-only): docs/domain/ssot/compose/mechanism-ssot/compose-fact-architecture.md;
process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.1, §11 (M1);
optional ``source`` field: compose-fact-first-k1-pd-design.md §3.
Wired into fact-first Init (Step 2 / Step 3 / Step 6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
_CORE = _SCRIPTS / "core"
for _p in (_SCRIPTS, _CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import (  # noqa: E402
    active_slice_dir,
    discussion_pointer_path,
)
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    filter_by_lens,
    lenses_present,
    load_facts,
    save_facts,
    unlensed_fact_ids,
    validate_facts,
)

_SESSION = _SCRIPTS / "schema" / "session"
if str(_SESSION) not in sys.path:
    sys.path.insert(0, str(_SESSION))


def _slice_dir(revision_dir: Path, *, target_l: str | None = None) -> Path:
    rev = Path(revision_dir).resolve()
    if target_l:
        tgt = str(target_l).strip()
        if not tgt:
            raise ValueError("target-l must be non-empty")
        return rev / tgt
    return active_slice_dir(rev)


def _multi_l_context(revision_dir: Path) -> tuple[bool, set[str]]:
    """Return (is_multi_l, allowed_home_ids). package always allowed with flag."""
    rev = Path(revision_dir).resolve()
    try:
        from dependency_tree_schema import (  # noqa: WPS433
            dependency_tree_path,
            load_dependency_tree,
        )
    except ImportError:
        return False, set()
    if not dependency_tree_path(rev).is_file():
        return False, set()
    try:
        tree = load_dependency_tree(rev)
    except (ValueError, OSError, json.JSONDecodeError):
        return False, set()
    if tree.get("status") != "locked":
        return False, set()
    ids = {str(n["id"]) for n in tree.get("nodes") or []}
    return len(ids) >= 2, ids


def _validate_home_l_write(
    facts: list[dict[str, Any]],
    *,
    revision_dir: Path,
    target_l: str | None,
    multi: bool,
    allowed_ids: set[str],
    package_confirm: bool,
) -> list[str]:
    errors: list[str] = []
    if not multi and not (target_l and target_l == "package"):
        return errors
    effective_target = target_l
    if multi and effective_target is None:
        try:
            from discussion_pointer_schema import load_discussion_pointer  # noqa: WPS433

            ptr = load_discussion_pointer(Path(revision_dir).resolve())
            effective_target = str(ptr.get("focus", "")).strip() or None
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
            effective_target = None
    for index, fact in enumerate(facts):
        prefix = f"facts[{index}]"
        home = fact.get("home_l")
        if home is None or (isinstance(home, str) and not home.strip()):
            errors.append(f"{prefix}: home_l required for multi-L / package write")
            continue
        home_s = str(home).strip()
        if home_s == "package":
            if not package_confirm:
                errors.append(
                    f"{prefix}: home_l=package requires --package-confirm "
                    "(human-only package bucket)"
                )
        elif home_s not in allowed_ids:
            errors.append(
                f"{prefix}: home_l {home_s!r} not in locked tree nodes "
                f"{sorted(allowed_ids)}"
            )
        if effective_target and home_s != effective_target:
            errors.append(
                f"{prefix}: home_l {home_s!r} must equal write target "
                f"{effective_target!r} (use --target-l <home_l> for G1 divert)"
            )
    if target_l == "package" and not package_confirm:
        errors.append("--target-l package requires --package-confirm")
    return errors


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


def cmd_write(args: argparse.Namespace) -> int:
    rev = Path(args.revision_dir).resolve()
    target_l = (args.target_l or "").strip() or None
    package_confirm = bool(getattr(args, "package_confirm", False))
    multi, allowed_ids = _multi_l_context(rev)
    if target_l == "package" and not package_confirm:
        return _fail("--target-l package requires --package-confirm")
    try:
        dest_dir = _slice_dir(rev, target_l=target_l)
    except ValueError as exc:
        return _fail(str(exc))
    if target_l:
        dest_dir.mkdir(parents=True, exist_ok=True)
    path = facts_path(dest_dir)
    try:
        if args.facts_file:
            raw = Path(args.facts_file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        facts = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read facts JSON: {exc}")

    if not isinstance(facts, list):
        return _fail("facts root must be a JSON array")

    home_errors = _validate_home_l_write(
        facts,
        revision_dir=rev,
        target_l=target_l,
        multi=multi,
        allowed_ids=allowed_ids,
        package_confirm=package_confirm,
    )
    if home_errors:
        return _fail("; ".join(home_errors))

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001 — surface fetch errors
            return _fail(f"section-registry unavailable: {exc}")

    try:
        save_facts(path, facts, allowed_lenses=allowed)
    except ValueError as exc:
        return _fail(str(exc))

    demote: dict[str, Any] | None = None
    if (
        target_l
        and target_l != "package"
        and discussion_pointer_path(rev).is_file()
    ):
        from discussion_pointer_control import cmd_demote_production  # noqa: WPS433
        import io
        from contextlib import redirect_stdout, redirect_stderr

        buf_out, buf_err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            code = cmd_demote_production(rev, target=target_l, confirm=True)
        raw_out = buf_out.getvalue().strip()
        if raw_out:
            try:
                demote = json.loads(raw_out)
            except json.JSONDecodeError:
                demote = {"ok": code == 0, "raw": raw_out}
        elif code != 0:
            return _fail(buf_err.getvalue().strip() or "demote-production failed")

    loaded = load_facts(path)
    payload: dict[str, Any] = {
        "ok": True,
        "command": "write",
        "path": str(path),
        "facts_total": len(loaded),
        "by_lens": lenses_present(loaded),
        "unlensed_total": len(unlensed_fact_ids(loaded)),
    }
    if target_l:
        payload["target_l"] = target_l
        payload["bucketed"] = True
    if demote is not None:
        payload["demote"] = demote
    return _ok(payload)


def cmd_filter(args: argparse.Namespace) -> int:
    path = facts_path(_slice_dir(args.revision_dir))
    try:
        facts = load_facts(path)
    except ValueError as exc:
        return _fail(str(exc))
    matched = filter_by_lens(facts, args.lens)
    if not matched:
        print(
            f"facts: no facts tagged lens={args.lens.strip().upper()}",
            file=sys.stderr,
        )
    print(json.dumps(matched, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = facts_path(_slice_dir(args.revision_dir))
    if not path.is_file():
        return _fail(f"facts file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    allowed = None
    if args.profile:
        try:
            allowed = _section_order(args.project_root.resolve(), args.profile.strip())
        except Exception as exc:  # noqa: BLE001
            return _fail(f"section-registry unavailable: {exc}")

    errors = validate_facts(data, allowed_lenses=allowed)
    if errors:
        return _fail("; ".join(errors))
    facts = load_facts(path)
    return _ok(
        {
            "ok": True,
            "command": "validate",
            "path": str(path),
            "facts_total": len(facts),
            "by_lens": lenses_present(facts),
            "unlensed_total": len(unlensed_fact_ids(facts)),
        }
    )


def cmd_status(args: argparse.Namespace) -> int:
    path = facts_path(_slice_dir(args.revision_dir))
    if not path.is_file():
        return _ok(
            {
                "ok": True,
                "command": "status",
                "exists": False,
                "path": str(path),
            }
        )
    try:
        facts = load_facts(path)
    except ValueError as exc:
        return _fail(str(exc))
    return _ok(
        {
            "ok": True,
            "command": "status",
            "exists": True,
            "path": str(path),
            "facts_total": len(facts),
            "by_lens": lenses_present(facts),
            "unlensed_total": len(unlensed_fact_ids(facts)),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser("write", help="Write validated _facts.json")
    write_p.add_argument("--revision-dir", type=Path, required=True)
    write_p.add_argument(
        "--facts-file",
        type=Path,
        help="Path to facts JSON array (default: stdin)",
    )
    write_p.add_argument(
        "--target-l",
        default="",
        help="Bucket into revision/<L>/_facts.json (or package/ with --package-confirm)",
    )
    write_p.add_argument(
        "--package-confirm",
        action="store_true",
        help="Human confirm for package-level bucket (AI must not self-select)",
    )
    write_p.add_argument("--profile", type=str, default="")
    write_p.add_argument("--project-root", type=Path, default=Path.cwd())
    write_p.set_defaults(func=cmd_write)

    filter_p = sub.add_parser(
        "filter",
        help="Print facts tagged with one lens as a JSON array (addressable, not prose)",
    )
    filter_p.add_argument("--revision-dir", type=Path, required=True)
    filter_p.add_argument("--lens", type=str, required=True)
    filter_p.set_defaults(func=cmd_filter)

    validate_p = sub.add_parser("validate", help="Validate _facts.json")
    validate_p.add_argument("--revision-dir", type=Path, required=True)
    validate_p.add_argument("--profile", type=str, default="")
    validate_p.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_p.set_defaults(func=cmd_validate)

    status_p = sub.add_parser("status", help="Facts presence and counts")
    status_p.add_argument("--revision-dir", type=Path, required=True)
    status_p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
