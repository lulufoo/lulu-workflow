#!/usr/bin/env python3
"""Control for compose Facts (``_facts.json``).

Subcommands:
    write          Persist facts JSON (AI-produced) after schema validation
    validate       Validate existing ``_facts.json``
    status         Print fact counts by lens tag (+ unlensed count)
    strip-derived  Remove ``origin.type=derived`` facts; no-op if none or missing file

    CLI details: ``python3 facts_control.py --help``

    ``write --target-l Lx`` buckets into ``revision/Lx/_facts.json``.
    Writes require the current unfrozen focus in FactIntake, Inductive, or Deductive.

Design rationale (source repo, why-only): docs/domain/ssot/compose/mechanism-ssot/compose-fact-architecture.md;
process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.1, §11 (M1);
optional ``source`` field: compose-fact-first-k1-pd-design.md §3.
Wired into fact-first Writing (Steps 2 and 6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
_KERNEL = _SCRIPTS / "_kernel"
for _p in (_SCRIPTS, _KERNEL):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from l_ledger_schema import active_slice_dir, load_l_ledger  # noqa: E402
from load_compose_template import load_compose_template  # noqa: E402
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    lenses_present,
    load_facts,
    normalize_fact,
    save_facts,
    strip_derived_facts,
    unlensed_fact_ids,
    validate_facts,
)
from compose_state_lock import compose_state_lock  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

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
    """Return (is_multi_l, allowed_home_ids) from the L ledger."""
    rev = Path(revision_dir).resolve()
    try:
        ledger = load_l_ledger(rev)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        return False, set()
    ids = {str(nid) for nid in ledger.get("order") or []}
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
            effective_target = str(
                load_l_ledger(Path(revision_dir).resolve()).get("focus", "")
            ).strip() or None
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
                f"{prefix}: home_l {home_s!r} not in ledger order "
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


def _section_order(
    project_root: Path,
    profile_id: str,
    *,
    profile_path: Path | None = None,
) -> list[str]:
    """Allowed lens keys from section-registry (``sections`` keys; archive-5.0)."""
    data = fetch_section_registry(
        project_root,
        profile_id=profile_id,
        profile_path=profile_path,
    )
    return lens_key_sequence(data)


def _consume_rule_ids(
    project_root: Path,
    profile_id: str,
    *,
    required: bool,
    profile_path: Path | None = None,
) -> list[str] | None:
    """Return consume_policy rule ids; None when absent and not required."""
    _SCOPE = _SCRIPTS / "schema" / "section" / "scope"
    if str(_SCOPE) not in sys.path:
        sys.path.insert(0, str(_SCOPE))
    from role_instance_schema import validate_role_instance  # noqa: WPS433

    raw = load_compose_template(
        "role-instance",
        project_root,
        profile_id=profile_id,
        profile_path=profile_path,
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("role-instance root must be an object")
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role-instance invalid: {'; '.join(errors)}")
    policy = data.get("consume_policy")
    if policy is None:
        if required:
            raise ValueError("role-instance missing consume_policy")
        return []
    rules = policy.get("rules") if isinstance(policy, dict) else None
    if not isinstance(rules, list) or not rules:
        if required:
            raise ValueError("role-instance consume_policy.rules must be non-empty")
        return []
    return [str(r["id"]).strip() for r in rules if isinstance(r, dict)]


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _runtime_profile(revision_dir: Path, project_root: Path):
    return resolve_revision_runtime_profile(
        Path(revision_dir),
        Path(project_root),
    )


def _require_producer_focus_write(revision_dir: Path, target_l: str | None) -> str | None:
    try:
        ledger = load_l_ledger(revision_dir)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return str(exc)
    focus = str(ledger["focus"])
    cell = ledger["by_id"][focus]
    if cell.get("frozen") is True:
        return f"focus {focus} is frozen"
    if cell.get("state") not in {"FactIntake", "Inductive", "Deductive"}:
        return (
            "facts write requires current unfrozen focus in FactIntake, Inductive, or Deductive "
            f"(focus {focus} is {cell.get('state')!r})"
        )
    if target_l and target_l not in {focus, "package"}:
        return (
            f"cannot write facts to {target_l}; current producer focus is {focus}"
        )
    return None


def cmd_write(args: argparse.Namespace) -> int:
    rev = Path(args.revision_dir).resolve()
    target_l = (args.target_l or "").strip() or None
    package_confirm = bool(getattr(args, "package_confirm", False))
    gate = _require_producer_focus_write(rev, target_l)
    if gate:
        return _fail(gate)
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
    intake_structure = bool(getattr(args, "intake_structure", False))
    require_seed_origin = bool(getattr(args, "require_seed_origin", False))
    if intake_structure and bool(getattr(args, "require_derivation", False)):
        return _fail("--intake-structure conflicts with --require-derivation")
    if require_seed_origin and not intake_structure:
        return _fail("--require-seed-origin requires --intake-structure")
    try:
        runtime = _runtime_profile(rev, args.project_root.resolve())
        allowed = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except Exception as exc:  # noqa: BLE001 — surface fetch errors
        return _fail(f"section-registry unavailable: {exc}")

    try:
        save_facts(
            path,
            facts,
            allowed_lenses=allowed,
            intake_structure=intake_structure,
            require_seed_origin=require_seed_origin,
        )
    except ValueError as exc:
        return _fail(str(exc))

    # intake_structure allows derivation without disposition; load_facts() does not.
    if intake_structure:
        loaded = [normalize_fact(entry) for entry in json.loads(path.read_text(encoding="utf-8"))]
    else:
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
    return _ok(payload)


def cmd_validate(args: argparse.Namespace) -> int:
    path = facts_path(_slice_dir(args.revision_dir))
    if not path.is_file():
        return _fail(f"facts file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON: {exc}")

    allowed = None
    allowed_rule_ids = None
    require_derivation = bool(getattr(args, "require_derivation", False))
    require_consume_policy = bool(getattr(args, "require_consume_policy", False))
    intake_structure = bool(getattr(args, "intake_structure", False))
    require_seed_origin = bool(getattr(args, "require_seed_origin", False))
    if intake_structure and require_derivation:
        return _fail("--intake-structure conflicts with --require-derivation")
    try:
        runtime = _runtime_profile(
            args.revision_dir.resolve(),
            args.project_root.resolve(),
        )
        allowed = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"section-registry unavailable: {exc}")
    if require_consume_policy or require_derivation:
        try:
            allowed_rule_ids = _consume_rule_ids(
                args.project_root.resolve(),
                runtime.profile_id,
                profile_path=runtime.profile_path,
                required=require_consume_policy,
            )
        except ValueError as exc:
            return _fail(str(exc))

    errors = validate_facts(
        data,
        allowed_lenses=allowed,
        allowed_rule_ids=allowed_rule_ids,
        require_derivation=require_derivation,
        intake_structure=intake_structure,
        require_seed_origin=require_seed_origin,
    )
    if errors:
        return _fail("; ".join(errors))
    # intake_structure allows derivation without disposition; load_facts() does not.
    if intake_structure:
        facts = [normalize_fact(entry) for entry in data]
    else:
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


def cmd_strip_derived(args: argparse.Namespace) -> int:
    path = facts_path(_slice_dir(args.revision_dir))
    if not path.is_file():
        return _ok(
            {
                "ok": True,
                "command": "strip-derived",
                "path": str(path),
                "exists": False,
                "removed": 0,
                "facts_total": 0,
            }
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    if not isinstance(raw, list) or not raw:
        return _ok(
            {
                "ok": True,
                "command": "strip-derived",
                "path": str(path),
                "exists": True,
                "removed": 0,
                "facts_total": 0 if not isinstance(raw, list) else len(raw),
            }
        )
    try:
        kept = strip_derived_facts(raw)
        if len(kept) != len(raw):
            save_facts(path, kept)
        return _ok(
            {
                "ok": True,
                "command": "strip-derived",
                "path": str(path),
                "exists": True,
                "removed": len(raw) - len(kept),
                "facts_total": len(kept),
            }
        )
    except ValueError as exc:
        return _fail(str(exc))


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
    write_p.add_argument("--project-root", type=Path, default=Path.cwd())
    write_p.add_argument(
        "--intake-structure",
        action="store_true",
        help=(
            "Fact-intake Cut: allow derivation without disposition; "
            "forbid disposition / origin.type=discovered"
        ),
    )
    write_p.add_argument(
        "--require-seed-origin",
        action="store_true",
        help="With --intake-structure: every fact origin.type must be seed",
    )
    write_p.set_defaults(func=cmd_write)

    validate_p = sub.add_parser("validate", help="Validate _facts.json")
    validate_p.add_argument("--revision-dir", type=Path, required=True)
    validate_p.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_p.add_argument(
        "--require-derivation",
        action="store_true",
        help="Every fact must carry derivation.disposition (Atomize path)",
    )
    validate_p.add_argument(
        "--require-consume-policy",
        action="store_true",
        help="Role must expose non-empty consume_policy.rules; bind not_needed.rule_id",
    )
    validate_p.add_argument(
        "--intake-structure",
        action="store_true",
        help=(
            "Fact-intake Cut/pre-Eval: require derivation.upstream_ref; "
            "forbid derivation.disposition and origin.type=discovered"
        ),
    )
    validate_p.add_argument(
        "--require-seed-origin",
        action="store_true",
        help="With --intake-structure: every fact origin.type must be seed",
    )
    validate_p.set_defaults(func=cmd_validate)

    status_p = sub.add_parser("status", help="Facts presence and counts")
    status_p.add_argument("--revision-dir", type=Path, required=True)
    status_p.set_defaults(func=cmd_status)

    strip_p = sub.add_parser(
        "strip-derived",
        help="Remove origin.type=derived facts; no-op if none",
    )
    strip_p.add_argument("--revision-dir", type=Path, required=True)
    strip_p.set_defaults(func=cmd_strip_derived)

    args = parser.parse_args()
    if args.command in {"write", "strip-derived"}:
        target = args.target_l if args.command == "write" else ""
        with compose_state_lock(_slice_dir(args.revision_dir, target_l=target or None)):
            return args.func(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
